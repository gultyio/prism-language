const std = @import("std");

const max_script_bytes = 1024 * 1024;
const max_entities = 256;

const Shape = enum {
    circle,
    square,
    triangle,
};

const Entity = struct {
    name: []const u8,
    shape: Shape,
    x: f64,
    y: f64,
    size: f64,
    color: []const u8,
};

const Scene = struct {
    title: []const u8 = "Prism Game",
    width: u32 = 800,
    height: u32 = 600,
    entities: std.ArrayList(Entity) = .empty,
};

fn printUsage() void {
    std.debug.print(
        \\Prism Engine - Prism-script scene runner
        \\Usage: PrismEngine <game.prism> [preview.svg]
        \\
        \\The preview path defaults to game.svg.
        \\
        \\Supported Prism commands:
        \\  game.scene;("Title");(800);(600)
        \\  game.entity;(player);(circle);(120);(180);(48);(#36a8ff)
        \\  game.move;(player);(20);(0)
        \\  game.destroy;(player)
        \\  h.printline;"Hello from Prism"
        \\
    , .{});
}

fn trimToken(token: []const u8) []const u8 {
    var result = std.mem.trim(u8, token, " \t\r\n");
    if (result.len >= 2 and
        ((result[0] == '"' and result[result.len - 1] == '"') or
        (result[0] == '\'' and result[result.len - 1] == '\'')))
    {
        result = result[1 .. result.len - 1];
    }
    return result;
}

fn parseGroups(line: []const u8, groups: *[8][]const u8) !usize {
    var count: usize = 0;
    var cursor: usize = 0;
    while (cursor < line.len) {
        if (line[cursor] != '(') {
            cursor += 1;
            continue;
        }
        if (count == groups.len) return error.TooManyArguments;

        const start = cursor + 1;
        cursor = start;
        var quote: ?u8 = null;
        while (cursor < line.len) : (cursor += 1) {
            const char = line[cursor];
            if (quote) |quote_char| {
                if (char == quote_char and (cursor == start or line[cursor - 1] != '\\')) {
                    quote = null;
                }
            } else if (char == '"' or char == '\'') {
                quote = char;
            } else if (char == ')') {
                break;
            }
        }
        if (cursor == line.len) return error.UnclosedArgument;
        groups[count] = trimToken(line[start..cursor]);
        count += 1;
        cursor += 1;
    }
    return count;
}

fn parseNumber(token: []const u8) !f64 {
    const value = try std.fmt.parseFloat(f64, trimToken(token));
    if (!std.math.isFinite(value)) return error.InvalidNumber;
    return value;
}

fn parsePositiveDimension(token: []const u8) !u32 {
    const value = try std.fmt.parseInt(u32, trimToken(token), 10);
    if (value == 0 or value > 16384) return error.InvalidSceneSize;
    return value;
}

fn isValidEntityName(name: []const u8) bool {
    if (name.len == 0 or !(std.ascii.isAlphabetic(name[0]) or name[0] == '_')) return false;
    for (name[1..]) |char| {
        if (!(std.ascii.isAlphanumeric(char) or char == '_' or char == '-')) return false;
    }
    return true;
}

fn findEntity(scene: *Scene, name: []const u8) ?usize {
    for (scene.entities.items, 0..) |entity, index| {
        if (std.mem.eql(u8, entity.name, name)) return index;
    }
    return null;
}

fn runScript(allocator: std.mem.Allocator, source: []const u8, scene: *Scene) !void {
    var scene_defined = false;
    const script = if (std.mem.startsWith(u8, source, "\xEF\xBB\xBF")) source[3..] else source;
    var lines = std.mem.splitScalar(u8, script, '\n');
    var line_number: usize = 0;

    while (lines.next()) |raw_line| {
        line_number += 1;
        const line = std.mem.trim(u8, raw_line, " \t\r\n");
        if (line.len == 0 or line[0] == '#') continue;

        if (std.mem.startsWith(u8, line, "c.comment(")) continue;
        if (std.mem.startsWith(u8, line, "h.printline;")) {
            const value = trimToken(line["h.printline;".len..]);
            std.debug.print("{s}\n", .{value});
            continue;
        }

        var groups: [8][]const u8 = undefined;
        const count = parseGroups(line, &groups) catch |err| {
            std.debug.print("Prism Engine: malformed arguments on line {d}: {s}\n", .{ line_number, @errorName(err) });
            return err;
        };

        if (std.mem.startsWith(u8, line, "game.scene;")) {
            if (count != 3) return error.InvalidSceneCommand;
            scene.title = groups[0];
            scene.width = try parsePositiveDimension(groups[1]);
            scene.height = try parsePositiveDimension(groups[2]);
            scene_defined = true;
        } else if (std.mem.startsWith(u8, line, "game.entity;")) {
            if (!scene_defined) return error.SceneMustBeDefinedFirst;
            if (count != 6) return error.InvalidEntityCommand;
            if (scene.entities.items.len >= max_entities) return error.TooManyEntities;
            if (!isValidEntityName(groups[0])) return error.InvalidEntityName;
            if (findEntity(scene, groups[0]) != null) return error.DuplicateEntityName;

            const shape = if (std.mem.eql(u8, groups[1], "circle"))
                Shape.circle
            else if (std.mem.eql(u8, groups[1], "square"))
                Shape.square
            else if (std.mem.eql(u8, groups[1], "triangle"))
                Shape.triangle
            else
                return error.UnsupportedShape;

            if (groups[5].len != 7 or groups[5][0] != '#') return error.InvalidColor;
            for (groups[5][1..]) |digit| {
                if (!std.ascii.isHex(digit)) return error.InvalidColor;
            }

            try scene.entities.append(allocator, .{
                .name = groups[0],
                .shape = shape,
                .x = try parseNumber(groups[2]),
                .y = try parseNumber(groups[3]),
                .size = try parseNumber(groups[4]),
                .color = groups[5],
            });
            if (scene.entities.items[scene.entities.items.len - 1].size <= 0) return error.InvalidEntitySize;
        } else if (std.mem.startsWith(u8, line, "game.move;")) {
            if (!scene_defined) return error.SceneMustBeDefinedFirst;
            if (count != 3) return error.InvalidMoveCommand;
            const index = findEntity(scene, groups[0]) orelse return error.EntityNotFound;
            scene.entities.items[index].x += try parseNumber(groups[1]);
            scene.entities.items[index].y += try parseNumber(groups[2]);
        } else if (std.mem.startsWith(u8, line, "game.destroy;")) {
            if (!scene_defined) return error.SceneMustBeDefinedFirst;
            if (count != 1) return error.InvalidDestroyCommand;
            const index = findEntity(scene, groups[0]) orelse return error.EntityNotFound;
            _ = scene.entities.orderedRemove(index);
        } else {
            std.debug.print("Prism Engine: unsupported Prism command on line {d}: {s}\n", .{ line_number, line });
            return error.UnsupportedCommand;
        }
    }

    if (!scene_defined) return error.SceneNotDefined;
}

fn appendFormatted(
    allocator: std.mem.Allocator,
    output: *std.ArrayList(u8),
    comptime format: []const u8,
    arguments: anytype,
) !void {
    const text = try std.fmt.allocPrint(allocator, format, arguments);
    defer allocator.free(text);
    try output.appendSlice(allocator, text);
}

fn appendXmlEscaped(allocator: std.mem.Allocator, output: *std.ArrayList(u8), text: []const u8) !void {
    for (text) |char| {
        const escaped = switch (char) {
            '&' => "&amp;",
            '<' => "&lt;",
            '>' => "&gt;",
            '"' => "&quot;",
            '\'' => "&apos;",
            else => null,
        };
        if (escaped) |replacement| {
            try output.appendSlice(allocator, replacement);
        } else {
            try output.append(allocator, char);
        }
    }
}

fn renderSvg(allocator: std.mem.Allocator, scene: *const Scene) ![]u8 {
    var output: std.ArrayList(u8) = .empty;
    errdefer output.deinit(allocator);

    try appendFormatted(allocator, &output,
        \\<svg xmlns="http://www.w3.org/2000/svg" width="{d}" height="{d}" viewBox="0 0 {d} {d}">
        \\<title>
    , .{ scene.width, scene.height, scene.width, scene.height });
    try appendXmlEscaped(allocator, &output, scene.title);
    try output.appendSlice(allocator,
        \\</title>
        \\<rect width="100%" height="100%" fill="#151923"/>
        \\
    );

    for (scene.entities.items) |entity| {
        switch (entity.shape) {
            .circle => try appendFormatted(allocator, &output,
                \\<circle id="{s}" cx="{d}" cy="{d}" r="{d}" fill="{s}"/>
                \\
            , .{ entity.name, entity.x, entity.y, entity.size / 2, entity.color }),
            .square => try appendFormatted(allocator, &output,
                \\<rect id="{s}" x="{d}" y="{d}" width="{d}" height="{d}" fill="{s}"/>
                \\
            , .{ entity.name, entity.x - entity.size / 2, entity.y - entity.size / 2, entity.size, entity.size, entity.color }),
            .triangle => try appendFormatted(allocator, &output,
                \\<polygon id="{s}" points="{d},{d} {d},{d} {d},{d}" fill="{s}"/>
                \\
            , .{
                entity.name,
                entity.x, entity.y - entity.size / 2,
                entity.x - entity.size / 2, entity.y + entity.size / 2,
                entity.x + entity.size / 2, entity.y + entity.size / 2,
                entity.color,
            }),
        }
    }

    try output.appendSlice(allocator, "</svg>\n");
    return output.toOwnedSlice(allocator);
}

fn run(init: std.process.Init) !void {
    var args = try init.minimal.args.iterateAllocator(init.gpa);
    defer args.deinit();
    _ = args.skip();

    const script_path = args.next() orelse {
        printUsage();
        return;
    };
    if (std.mem.eql(u8, script_path, "--help") or std.mem.eql(u8, script_path, "-h")) {
        printUsage();
        return;
    }
    const output_path = args.next() orelse "game.svg";
    if (args.next() != null) return error.TooManyCommandLineArguments;

    const source = try std.Io.Dir.cwd().readFileAlloc(
        init.io,
        script_path,
        init.gpa,
        .limited(max_script_bytes),
    );
    defer init.gpa.free(source);

    var scene: Scene = .{};
    defer scene.entities.deinit(init.gpa);
    try runScript(init.gpa, source, &scene);

    const svg = try renderSvg(init.gpa, &scene);
    defer init.gpa.free(svg);
    try std.Io.Dir.cwd().writeFile(init.io, .{
        .sub_path = output_path,
        .data = svg,
    });

    std.debug.print(
        "Prism Engine: rendered \"{s}\" ({d}x{d}, {d} entities) to {s}\n",
        .{ scene.title, scene.width, scene.height, scene.entities.items.len, output_path },
    );
}

pub fn main(init: std.process.Init) void {
    run(init) catch |err| {
        std.debug.print("Prism Engine error: {s}\n", .{@errorName(err)});
        std.process.exit(1);
    };
}
