from lark import Lark
from webtest.context import ctx
from webtest.commands.handlers import command_handlers
from webtest.browser_setup import browser_init
import argparse

grammar_path = "webtest/grammar.lark"
ctx.parser = Lark.open(
    grammar_path,
    parser="lalr",
)

def run_webtest(file_path, headless=True):
    with open(file_path, "r") as file:
        script = file.read()

    tree = ctx.parser.parse(script)

    def execute_commands():
        for cmd in tree.children:
            handler = command_handlers.get(cmd.children[0].data)
            if handler:
                handler(cmd)
            else:
                print(f"command not supported: {cmd.children[0].data}")

    browser_init(execute_commands, headless=headless)

def cli_entry():
    parser = argparse.ArgumentParser(description="Run a .webtest script")
    parser.add_argument("file_path", help="Path to the .webtest file")
    parser.add_argument("-H", "--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()
    path = f"tests/{args.file_path}.webtest"

    run_webtest(path, headless=args.headless)
