from webtest.utils import generate_mocked_data, resolve_selector, get_unique_locator, resolve_selectors, assert_all_unique_and_visible
from lark import Token
from pathlib import Path
import yaml
from webtest.context import ctx
from webtest.utils import load_functions
import time

command_handlers = {}
variables = {}

def register(name):
    def decorator(funct):
        command_handlers[name] = funct
        return funct
    return decorator

@register("visit")
def handle_visit(cmd, page):
    import tldextract
    url = cmd.children[0].children[0].value.strip()
    print(f"[VISIT] {url}")
    page.goto(url)
    ready_state = page.evaluate("() => document.readyState")
    if ready_state == "complete":
        ext = tldextract.extract(url)
        assert ext.domain in page.url, f"something went wrong with URL, expected URL: {url}, actual URL {page.url}"

@register("click")
def handle_click(cmd, page):
    children = cmd.children[0].children
    variable = children[0]

    defined_locator = resolve_selector(variable, "[CLICK - ERROR]")
    locator, _ = get_unique_locator(page, defined_locator, "[CLICK - ERROR]", require_clickable=True)

    if len(children) > 1:
        number = int(children[1]) - 1
        locator = locator.nth(number)

    try:
        print(f"[CLICK] {variable}")
        locator.click()
    except Exception as e:
        print(f"[CLICK - ERROR] tried to click but an error occured: {e}")
        raise


@register("fill")
def handle_fill(cmd, page):
    variable = cmd.children[0].children[0]

    defined_locator = resolve_selector(variable, "[FILL - ERROR]")
    valid_fills = {"tag": {"input", "textarea"},
                   "type": {"text", "email", "password", "search", "url", "''"}}
    locator, _ = get_unique_locator(page, defined_locator, "[FILL - ERROR]")
    entered_text = cmd.children[0].children[1].value.strip('"')

    if "mocked:" in entered_text:
        text = generate_mocked_data(entered_text)
    elif "var:" in entered_text:
        variable_name = entered_text.split(":")[1]

        if not variable_name in variables:
            raise Exception(f"[FILL] error, vairable '{variable_name}' not defined")

        text = variables[variable_name]
    else:
        text = entered_text

    tag = locator.evaluate("element => element.tagName.toLowerCase()")

    if tag in valid_fills["tag"] and (tag == "input" and locator.get_attribute("type") in valid_fills["type"]) or tag == "textarea":
        print(f"[FILL] {variable} [WITH] '{text}'")
        locator.fill(text)

@register("check_page")
def handle_check_page(cmd, page):
    page_name = " ".join(token.value for token in cmd.children[0].children if isinstance(token, Token) and token.type == "NAME")
    rows = cmd.children[0].children[1].children
    entered_locators = {row.value.strip() for row in rows}

    verified_locators = resolve_selectors(entered_locators, "[VERIFY-PAGE - ERROR]")
    
    assert_all_unique_and_visible(page, verified_locators, "[VERIFY-PAGE - ERROR]")

    print(f"[VERIFY-PAGE] {page_name} page loaded correctly")

@register("element_visible")
def handle_element_visible(cmd, page):
    children = cmd.children[0]
    variable = children.children[0].value.strip()
    present_or_not = children.children[1].value.strip()
    
    defined_locator = resolve_selector(variable, "[ELEMENT-VISIBLE - ERROR]")
    _, element_is_visible = get_unique_locator(page, defined_locator, "[ELEMENT-VISIBLE - ERROR]")

    if present_or_not == "is":
        if not element_is_visible:
            raise Exception(f"[ELEMENT-VISIBLE - ERROR] element {variable} is not visible")
        print(f"[ELEMENT-VISIBLE] element {variable} is visible in page")
    else:
        if element_is_visible:
            raise Exception(f"[ELEMENT-VISIBLE - ERROR] element {variable} is visible but shouldn't be")
        print(f"[ELEMENT-VISIBLE] element {variable} is not visible in page")

@register("define_locator")
def handle_define(cmd, _):
    children = cmd.children[0]
    defined_locator = children.children[1].value.strip()
    variable = children.children[0].value.strip()
    if variable in ctx.locator_map:
        print(f"[MERGE-ALERT] merging already defined locators, {variable} locator was already defined")
    ctx.locator_map[variable] = defined_locator

@register("fill_form")
def handle_fill_form(cmd, page):
    rows = cmd.children[0].children
    variable_locators = {token.value.strip() for token in rows if isinstance(token, Token) and token.type == "NAME"}
    resolve_selectors(variable_locators, "[FILL-FORM - ERROR]")

    for i in range(0, len(rows), 2):
        locator_variable_name = rows[i].value.strip()
        entered_locator = resolve_selector(locator_variable_name, "[FILL-FORM - ERROR]")
        entered_text = rows[i + 1].value.strip('"')

        if "mocked:" in entered_text:
            text = generate_mocked_data(entered_text)
        elif "var:" in entered_text:
            variable_name = entered_text.split(":")[1]

            if not variable_name in variables:
                raise Exception(f"[FILL-FORM - ERROR] vairable {variable_name} not defined")

            text = variables[variable_name]
        else:
            text = entered_text

        page_locator, _ = get_unique_locator(page, entered_locator, "[FILL-FORM - ERROR]")

        valid_fills = { "tag": {"input", "textarea"},
                        "type": {"text", "email", "password", "search", "url", "''"}}

        tag = page_locator.evaluate("element => element.tagName.toLowerCase()")
        if not (tag in valid_fills["tag"] and (tag == "input" and page_locator.get_attribute("type") in valid_fills["type"]) or tag == "textarea"):
            raise Exception(f"[FILL-FORM - ERROR] locator '{locator_variable_name}' is not fillable with data")

        page_locator.fill(text) 

    print(f"[FILL-FORM] form filled successfully")

@register("select_tag")
def handle_select(cmd, page):
    children = cmd.children[0]
    option_to_select = children.children[0].value.strip('"')
    locator_variable = children.children[1].value.strip()

    defined_locator = resolve_selector(locator_variable, "[SELECT - ERROR]")
    page_locator,_ = get_unique_locator(page, defined_locator, "[SELECT - ERROR]")

    tag = page_locator.evaluate("element => element.tagName.toLowerCase()") == "select"
    if not tag:
        raise Exception(f"[SELECT - ERROR] element {locator_variable} is not a select element")

    options = page_locator.locator("option").all_text_contents()
    if not option_to_select in options:
        raise Exception(f"[SELECT - ERROR] {option_to_select} not in options")

    try:
        page_locator.select_option(label=option_to_select)
    except Exception as e:
        print(f"[SELECT - ERROR] something happened when selecting option: {e}")
        raise

    print(f"[SELECT] '{option_to_select}' option selected")

@register("select_list")
def select_list_handler(cmd, page):
    rows = cmd.children[0].children
    variable_locators = {token.value.strip() for token in rows if isinstance(token, Token) and token.type == "NAME"}
    resolve_selectors(variable_locators, "[SELECT-LIST - ERROR]")

    for i in range(0, len(rows), 2):
        entered_variable_name = rows[i].value.strip()
        solved_locator = resolve_selector(entered_variable_name, "[SELECT-LIST - ERROR]")
        option_to_select = rows[i + 1].value.strip('"')
        defined_locator,_ = get_unique_locator(page, solved_locator, "[SELECT-LIST - ERROR]")

        tag = defined_locator.evaluate("element => element.tagName.toLowerCase()") == "select"
        if not tag:
            raise Exception(f"[SELECT-LIST - ERROR] element {entered_variable_name} is not a select element")

        try:
            defined_locator.select_option(label=option_to_select)
        except Exception as e:
            print(f"[SELECT-LIST - ERROR] something happened when selecting option {entered_variable_name}, error: {e}")

    print(f"[SELECT-LIST] all options selected")

@register("checkbox_check")
def check_uncheck_handler(cmd, page):
    children = cmd.children[0]
    action = children.children[0].value.strip()
    entered_locator = children.children[1].value.strip()
    label = "[CHECK]" if action == "check" else "[UNCHECK]"
    label_error = "[CHECK - ERROR]" if action == "check" else "[UNCHECK - ERROR]"

    valid_checks = {"tag": "input",
                    "type": {"checkbox", "radio"}}

    defined_locator = resolve_selector(entered_locator, label_error)
    page_locator,_= get_unique_locator(page, defined_locator, label_error)

    tag = page_locator.evaluate("element => element.tagName.toLowerCase()")
    attribute = page_locator.get_attribute("type")

    if not (tag in valid_checks["tag"] and attribute in valid_checks["type"]):
        raise Exception(f"{label_error} locator {entered_locator} is not checkbox or radio")

    checked = page_locator.is_checked()
    if action == "check":
        if not checked:
            page_locator.check()
    elif action == "uncheck":
        if attribute == "radio":
            raise Exception(f"{label_error} {entered_locator} is type radio, can't uncheck")
        if checked:
            page_locator.uncheck()

    print(f"{label} element {entered_locator}")

@register("text_visible")
def handle_text_visible(cmd, page):
    children = cmd.children[0]
    entered_text = children.children[1].value.strip('"')

    if entered_text.startswith("var:"):
        variable = entered_text.split(":")[1]

        if variable not in variables:
            raise Exception(f"[CHECK-TEXT - ERROR] variable {variable} not defined")
        entered_text = variables[variable]

    entered_tag = children.children[2].value.strip("<>")
    present_in_page = children.children[3].value.strip('"')
    text_to_look = f"//{entered_tag}[contains(text(), '{entered_text}')]"
    _, text_is_visible = get_unique_locator(page, text_to_look, "[CHECK-TEXT - ERROR]")

    if present_in_page == "is":
        if not text_is_visible:
            raise Exception(f"[CHECK-TEXT - ERROR] text '{entered_text}' is not visible")
        print(f"[CHECK-TEXT] text '{entered_text}' is visible in page")
    else:
        if text_is_visible:
            raise Exception(f"[CHECK-TEXT - ERROR] text '{entered_text}' is visible but shouldn't be")
        print(f"[CHECK-TEXT] text '{entered_text}' is not visible in page")

@register("import_locators")
def handle_import_locators(cmd, _):
    filename = cmd.children[0].children[0].value.strip()
    locators_path = Path(f"tests/locators/{filename}.yaml")

    if not locators_path.exists():
        raise FileNotFoundError(f"[IMPORT-LOCATORS] failed, file not found: {locators_path}, file should be [filename].yaml inside a 'locators' folder inside tests folder")

    with open(locators_path, "r", encoding="utf-8") as f:
        locators = yaml.safe_load(f)

        if not isinstance(locators, dict):
            raise ValueError("[IMPORT-LOCATORS] YAML format invalid (must be key-value)")
        
        already_in_locator_map = {locator for locator in locators.keys() if locator in ctx.locator_map}
        if already_in_locator_map:
            print(f"[MERGE-ALERT] merging already defined locators: {already_in_locator_map}")

        ctx.locator_map.update(locators)

@register("use_function")
def handle_define_function(cmd, page):
    entered_function_name = cmd.children[0].children[0].value.strip()

    if not ctx.functions:
        ctx.functions = load_functions("tests/functions/common_functions.txt")

    if entered_function_name not in ctx.functions:
        raise Exception(f"[IMPORT-MACRO] failed, '{entered_function_name}' macro does not exist")

    body = ctx.functions[entered_function_name]
    subtree = ctx.parser.parse(body)
    commands = subtree.children

    for command in commands:
        decorator_name = command.children[0].data
        command_handlers[decorator_name](command, page)


@register("save_variable")
def handle_save_variable(cmd, page):
    children = cmd.children[0].children
    to_save_in_variable = children[0].value.strip('"')
    entered_variable_name = children[1].value.strip()

    if to_save_in_variable.startswith("mocked:"):
        to_save_in_variable = generate_mocked_data(to_save_in_variable)
    elif to_save_in_variable.startswith("txt:"):
        variable_locator = resolve_selector(to_save_in_variable.split(":")[1], "[SAVE-VARIABLE - ERROR]")
        entered_variable_name = children[2].value.strip()

        defined_locator = ctx.locator_map[variable_locator]
        locator = page.locator(defined_locator)
        matches = locator.count()

        if matches == 0:
            raise Exception(f"[SAVE-VARIABLE - ERROR] locator '{variable_locator}' does not match any element")

        if len(children) > 2:
            number = int(children[1]) - 1
            locator = locator.nth(number)
        else:
            if matches > 1:
                raise Exception(f"[CLICK - ERROR] locator '{defined_locator}' got {matches} matches, please define a more specific locator")

        if not locator.is_visible():
            raise Exception(f"[SAVE-VARIABLE - ERROR] locator found but not visible: '{variable_locator}'")

        to_save_in_variable = locator.text_content()

    variables[entered_variable_name] = to_save_in_variable

@register("upload_file")
def handle_upload_file(cmd, page):
    entered_file_name = cmd.children[0].children[0].value.strip('"')
    locator_variable = cmd.children[0].children[1].value.strip()
    file_path = Path(f"tests/files/{entered_file_name}")

    if not file_path.exists():
        raise Exception(f"[UPLOAD-FILE] error, file '{entered_file_name}' not found")

    if not locator_variable in ctx.locator_map:
        raise Exception(f"[UPLOAD-FILE] error, '{locator_variable}' not declared")

    page_locator = page.locator(ctx.locator_map[locator_variable])
    tag = page_locator.evaluate("element => element.tagName.toLowerCase()")

    if tag != "input" or page_locator.get_attribute("type") != "file":
        raise Exception(f"[UPLOAD-FILE] failed, element is not an input or is an input but not type file")

    if not (page_locator.is_visible() and page_locator.count() > 0):
        raise Exception(f"[UPLOAD-FILE] failed, locator not found or not visible: {locator_variable}: {ctx.locator_map[locator_variable]}")

    page.set_input_files(ctx.locator_map[locator_variable], file_path)

#FIXME
# @register("accept_dismiss")
# def handle_accept_dismiss(cmd, page):
#     print(cmd)

@register("wait")
def handle_wait(cmd,_):
    seconds_to_wait = cmd.children[0].children[0].value
    time.sleep(int(seconds_to_wait))
    print(f"[WAIT] waited for {seconds_to_wait} seconds")

@register("assert_match")
def handle_assert_match(cmd, page):
    children = cmd.children[0].children
    pair = []
    i = 0
    if len(children) > 2:
        while i < len(children):
            if children[i].type == "COMPLEX_VALUE":
                value = children[i].value.strip('"')
                number = children[i + 1] if i + 1 < len(children) else None
                if value.startswith("txt:"):
                    variable_name = resolve_selector(value.split(":")[1], "[ASSERT - ERROR]")
                    variable_locator = get_unique_locator(page, variable_name, "[ASSERT - ERROR]")
                    num = int(number) - 1
                    locator = locator.nth(num)
                    pair.append(locator.text_content())
                    i += 2 if number else 1
                else:
                    pair.append(value)
                    i += 1
            else: 
                i += 1
    else:
        maybe_num = lambda s: int(s) if s.isdigit() else s
        def has_variable_or_txt(value, page):
            to_return = value
            if value.startswith("var:"):
                variable_name = value.split(":")[1]
                if variable_name not in variables:
                    raise Exception(f"[ASSERT - ERROR] '{variable_name}' not defined")
                to_return = variables[variable_name]
            elif value.startswith("txt:"):
                variable_name = resolve_selector(value.split(":")[1], "[ASSERT - ERROR]")
                defined_locator = get_unique_locator(page, variable_name, "[ASSERT - ERROR]")
                to_return = defined_locator.text_content()
            return to_return

        first_value = maybe_num(has_variable_or_txt(children[0].value.strip('"'), page))
        second_value = maybe_num(has_variable_or_txt(children[1].value.strip('"'), page))

        if not first_value == second_value:
            raise Exception(f"[ASSERT - ERROR] '{first_value}' is different that '{second_value}'")

        print(f"[ASSERT] '{first_value}' matches with '{second_value}'")
