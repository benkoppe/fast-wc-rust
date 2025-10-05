import random
import os

# Common C/C++ keywords and identifiers
keywords = [
    "int",
    "char",
    "float",
    "double",
    "void",
    "if",
    "else",
    "for",
    "while",
    "do",
    "switch",
    "case",
    "break",
    "continue",
    "return",
    "struct",
    "union",
    "enum",
    "typedef",
    "const",
    "static",
    "extern",
    "auto",
    "register",
    "volatile",
    "sizeof",
    "include",
    "define",
    "ifdef",
    "ifndef",
    "endif",
    "pragma",
]

common_vars = [
    "i",
    "j",
    "k",
    "n",
    "count",
    "size",
    "length",
    "index",
    "value",
    "data",
    "buffer",
    "ptr",
    "temp",
    "result",
    "status",
    "error",
    "flag",
    "max",
    "min",
    "sum",
    "total",
    "average",
    "current",
    "next",
    "prev",
    "first",
    "last",
    "start",
    "end",
]

function_names = [
    "main",
    "init",
    "cleanup",
    "process",
    "calculate",
    "validate",
    "parse",
    "format",
    "convert",
    "compare",
    "search",
    "sort",
    "insert",
    "delete",
    "update",
    "create",
    "destroy",
    "allocate",
    "free",
    "copy",
    "move",
    "swap",
    "print",
    "read",
    "write",
    "open",
    "close",
    "send",
    "receive",
]

types = [
    "int",
    "char",
    "float",
    "double",
    "long",
    "short",
    "unsigned",
    "signed",
    "bool",
    "size_t",
    "uint32_t",
    "int64_t",
    "FILE",
    "struct",
    "void",
]


def generate_c_content(lines):
    content = []
    content.append("#include <stdio.h>")
    content.append("#include <stdlib.h>")
    content.append("#include <string.h>")
    content.append("#include <math.h>")
    content.append("")

    for i in range(lines - 10):
        line_type = random.choice(
            [
                "function_def",
                "variable_decl",
                "assignment",
                "if_stmt",
                "for_loop",
                "comment",
                "function_call",
            ]
        )

        if line_type == "function_def":
            ret_type = random.choice(types)
            func_name = random.choice(function_names) + str(random.randint(1, 100))
            params = ", ".join(
                [
                    f"{random.choice(types)} {random.choice(common_vars)}"
                    for _ in range(random.randint(0, 3))
                ]
            )
            content.append(f"{ret_type} {func_name}({params}) {{")

        elif line_type == "variable_decl":
            var_type = random.choice(types)
            var_name = random.choice(common_vars) + str(random.randint(1, 50))
            if random.choice([True, False]):
                content.append(
                    f"    {var_type} {var_name} = {random.randint(0, 1000)};"
                )
            else:
                content.append(f"    {var_type} {var_name};")

        elif line_type == "assignment":
            var1 = random.choice(common_vars)
            var2 = random.choice(common_vars)
            op = random.choice(["+", "-", "*", "/", "%", "&", "|", "^"])
            content.append(f"    {var1} = {var2} {op} {random.randint(1, 100)};")

        elif line_type == "if_stmt":
            var1 = random.choice(common_vars)
            var2 = random.choice(common_vars)
            comp = random.choice(["==", "!=", "<", ">", "<=", ">="])
            content.append(f"    if ({var1} {comp} {var2}) {{")
            content.append(
                f"        {random.choice(common_vars)} = {random.randint(0, 100)};"
            )
            content.append("    }")

        elif line_type == "for_loop":
            var = random.choice(["i", "j", "k"])
            limit = random.choice(common_vars)
            content.append(f"    for (int {var} = 0; {var} < {limit}; {var}++) {{")
            content.append(
                f"        {random.choice(function_names)}({random.choice(common_vars)});"
            )
            content.append("    }")

        elif line_type == "comment":
            words = [
                random.choice(keywords + common_vars + function_names)
                for _ in range(random.randint(3, 10))
            ]
            content.append(f"    // {' '.join(words)}")

        elif line_type == "function_call":
            func = random.choice(function_names)
            args = ", ".join(
                [random.choice(common_vars) for _ in range(random.randint(0, 3))]
            )
            content.append(f"    {func}({args});")

    content.append("}")
    return "\n".join(content)


def generate_h_content(lines):
    content = []
    content.append("#ifndef HEADER_H")
    content.append("#define HEADER_H")
    content.append("")
    content.append("#include <stdio.h>")
    content.append("#include <stdlib.h>")
    content.append("")

    for i in range(lines - 10):
        line_type = random.choice(
            ["function_decl", "define", "typedef", "struct", "comment"]
        )

        if line_type == "function_decl":
            ret_type = random.choice(types)
            func_name = random.choice(function_names) + str(random.randint(1, 100))
            params = ", ".join(
                [
                    f"{random.choice(types)} {random.choice(common_vars)}"
                    for _ in range(random.randint(0, 3))
                ]
            )
            content.append(f"{ret_type} {func_name}({params});")

        elif line_type == "define":
            name = random.choice(common_vars).upper() + str(random.randint(1, 100))
            value = random.randint(1, 1000)
            content.append(f"#define {name} {value}")

        elif line_type == "typedef":
            old_type = random.choice(types)
            new_type = random.choice(common_vars) + "_t"
            content.append(f"typedef {old_type} {new_type};")

        elif line_type == "struct":
            struct_name = random.choice(common_vars) + "_struct"
            content.append(f"struct {struct_name} {{")
            for _ in range(random.randint(2, 5)):
                field_type = random.choice(types)
                field_name = random.choice(common_vars)
                content.append(f"    {field_type} {field_name};")
            content.append("};")

        elif line_type == "comment":
            words = [
                random.choice(keywords + common_vars + function_names)
                for _ in range(random.randint(3, 10))
            ]
            content.append(f"/* {' '.join(words)} */")

    content.append("")
    content.append("#endif")
    return "\n".join(content)


# Generate large files
os.makedirs("generated_input", exist_ok=True)

# Create multiple large .c files (50K-100K lines each)
for i in range(50):
    lines = random.randint(50000, 100000)
    filename = f"sample_input/large_file_{i+1}.c"
    print(f"Generating {filename} with {lines} lines...")
    with open(filename, "w") as f:
        f.write(generate_c_content(lines))

# Create multiple large .h files (20K-50K lines each)
for i in range(30):
    lines = random.randint(20000, 50000)
    filename = f"sample_input/large_header_{i+1}.h"
    print(f"Generating {filename} with {lines} lines...")
    with open(filename, "w") as f:
        f.write(generate_h_content(lines))

print("Done generating large test files!")
