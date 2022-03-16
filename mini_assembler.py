import re
import pprint


class Instruction:
    """Class representing a single line in a program"""
    def __init__(self, line_no, key, match):
        self.line_no = line_no
        self.key = key

        if key == "jump_zero":
            self.value_one = match[1]
            self.jump_to = int(match[2])
        if key in ("inc", "dec", "set_zero"):
            self.value_one = match[1]
        if key == "jump":
            self.jump_to = int(match[1])
        if key in ("transfer", "add"):
            self.value_one = match[1]
            self.value_two = match[2]
        if key == "abs_diff":
            self.value_one = match[1]
            self.value_two = match[2]
            self.value_three = match[3]

    def __repr__(self):
        values = {}
        for value in ["value_one", "value_two", "value_three", "jump_to"]:
            try:
                values[value] = getattr(self, value)
            except AttributeError:
                pass

        value_strings = [f"{key}={value}" for key, value in values.items()]
        value_strings.insert(0, f"key={self.key}")  # Prepend
        return f"<Instruction {', '.join(value_strings)}>"


class AssemblyParser:
    """Class to parse mini assembler

    The only instructions that are recognised are:
    * if (x == 0) goto line_no
    * x = x + 1
    * x = x - 1
    * goto line_no
    * stop
    * x = 0

    Some extensions which are recognised are:
    * x = y
    * x = x + y
    * z = abs(x - y)

    To enable any of these, a numeric flag must be passed when initialising
    which indicates which one plus all the ones before it should be recognised.
    The default is -1, which enables none of the extenstions.

    Only variables that are one character long and in the ranges a-z or A-Z are valid.
    """
    basic_instructions = {
        "jump_zero": r"if \(([a-zA-Z]) == 0\) goto (\d+)",
        "inc": r"([a-zA-Z]) = \1 \+ 1",
        "dec": r"([a-zA-Z]) = \1 \- 1",
        "jump": r"goto (\d+)",
        "halt": r"stop",
        "set_zero": r"([a-zA-Z]) = 0"
    }

    ext_instructions = {
        "transfer": r"([a-zA-Z]) = ([a-zA-Z])",
        "add": r"([a-zA-Z]) = \1 \+ ([a-zA-Z])",
        "abs_diff": r"([a-zA-Z]) = abs\(([a-zA-Z]) - ([a-zA-Z])\)"
    }

    def __init__(self, file, start_state=None, ext=-1):
        """Creates parser for a file

        You can enable extension instructions with a ext kwarg greater than or equal to 0

        A original state for the variables used in the program can be passed in using start_state.
        Eg: start_state = {"x": 2, "y": 5}
        """
        self.file = file
        self.ext = 0
        self.instructions = {}
        self.start_state = start_state

    def parse_assembly(self):
        with open(self.file, "r") as file:
            # Find and parse all instructions
            for line in file:
                if line.startswith("//"):
                    continue

                line_match = re.match(r"\((\d+)\) (.*)", line)
                if not line_match:
                    raise SyntaxError("No line number provided")

                line_number = int(line_match[1])
                code = line_match[2]

                if self.instructions.get(line_number):
                    raise SyntaxError("Duplicate line number")

                found = False

                for key, regex in self.basic_instructions.items():
                    instruction_match = re.fullmatch(regex, code.strip())
                    if instruction_match:
                        self.instructions[line_number] = Instruction(
                            line_no=line_number, key=key,
                            match=instruction_match)
                        found = True
                        break

                if found:
                    continue

                for i, (key, regex) in enumerate(self.ext_instructions.items()):
                    if not i <= self.ext:
                        break

                    instruction_match = re.fullmatch(regex, code.strip())
                    if instruction_match:
                        self.instructions[line_number] = Instruction(
                            line_no=line_number, key=key,
                            match=instruction_match)
                        found = True
                        break

                if not found:
                    raise SyntaxError(f"No matching instruction could be found for the line: {code.strip()}")

        # Create dict with all variables mentioned in the instructions parsed
        self.variables = set()
        for instruction in self.instructions.values():
            for value in ["value_one", "value_two", "value_three"]:
                try:
                    self.variables.add(getattr(instruction, value))
                except AttributeError:
                    pass

        self.variables = {key: None for key in self.variables}
        if self.start_state:
            for key, value in self.start_state.items():
                self.variables[key] = value

        keys = list(self.instructions.keys())
        for i, key in enumerate(keys):
            if i + 1 != key:
                raise SyntaxError("Line numbers must range from one upwards and increment by one each time")

    @staticmethod
    def instruction_generator(limit=300):
        instruction = 1
        count = 0
        while True:
            if count > limit:
                break

            jump = (yield instruction)

            if jump is not None:
                instruction = jump - 1
            else:
                instruction += 1

            count += 1

    def run(self, verbose=False):
        generator = self.instruction_generator()
        for i in generator:
            try:
                inst = self.instructions[i]
            except KeyError:
                raise KeyError(f"Jumped to line: {i} which does not exist")

            if inst.key == "jump_zero":
                if self.variables[inst.value_one] == 0:
                    generator.send(inst.jump_to)
                if verbose:
                    print(f"{i}: Jump to {inst.jump_to} if {inst.value_one} is 0")

            if inst.key == "inc":
                if self.variables[inst.value_one] is None:
                    raise TypeError(f"Incrementing a variable with no default on line: {i}")

                self.variables[inst.value_one] += 1
                if verbose:
                    print(f"{i}: Increment {inst.value_one}")

            if inst.key == "dec":
                if self.variables[inst.value_one] is None:
                    raise TypeError(f"Decrementing a variable with no default on line: {i}")

                self.variables[inst.value_one] -= 1
                if verbose:
                    print(f"{i}: Decrement {inst.value_one}")

            if inst.key == "jump":
                generator.send(inst.jump_to)
                if verbose:
                    print(f"{i}: Jump to {inst.jump_to}")

            if inst.key == "halt":
                if verbose:
                    print(f"{i}: Halting")
                break

            if inst.key == "set_zero":
                self.variables[inst.value_one] = 0
                if verbose:
                    print(f"{i}: Setting {inst.value_one} to zero")

            if inst.key == "transfer":
                self.variables[inst.value_one] = self.variables[inst.value_two]
                if verbose:
                    print(f"{i}: Setting {inst.value_one} to the value in {inst.value_two}")

            if inst.key == "add":
                # x = x + y
                x = self.variables[inst.value_one]
                self.variables[inst.value_one] = x + self.variables[inst.value_two]
                if verbose:
                    print(f"{i}: Setting {inst.value_one} to {inst.value_one} + {inst.value_two}")

            if inst.key == "abs_diff":
                # z = abs(x - y)
                x = self.variables[inst.value_two]
                y = self.variables[inst.value_three]
                self.variables[inst.value_one] = abs(x - y)
                if verbose:
                    print(f"{i}: Setting {inst.value_one} to abs({inst.value_two} - {inst.value_three})")


if __name__ == "__main__":
    parser = AssemblyParser("mini-assembler-1.txt", start_state={"y": 5})
    parser.parse_assembly()

    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(parser.instructions)
    pp.pprint(parser.variables)

    parser.run()

    pp.pprint(parser.variables)
