from webtest.utils import resolve_selector, get_locator, resolve_selectors, assert_all_unique_and_visible, resolve_prefix
from lark import Token
from pathlib import Path
import yaml
from webtest.context import ctx
from webtest.utils import load_functions
import time

command_handlers = {}

def register(name):
    def decorator(funct):
        command_handlers[name] = funct
        return funct
    return decorator

@register("visit")
def handle_visit(cmd):
    import tldextract
    url = cmd.children[0].children[0].value.strip()
    ctx.page.goto(url)
    ready_state = ctx.page.evaluate("() => document.readyState")
    if ready_state == "complete":
        ext = tldextract.extract(url)
        assert ext.domain in ctx.page.url, f"something went wrong with URL, expected URL: {url}, actual URL {ctx.page.url}"
    print(f"[VISIT] {url}")

@register("click")
def handle_click(cmd):
    children = cmd.children[0].children
    variable = children[0]
    index = int(children[1]) - 1 if len(children) > 1 else None
    unique_needed = index is None
    defined_locator = resolve_selector(variable, "[CLICK - ERROR]")

    locator,_ = get_locator(defined_locator, "[CLICK - ERROR]", require_clickable=True, unique=unique_needed, loc_number=index)

    try:
        print(f"[CLICK] {variable}")
        locator.click()
    except Exception as e:
        print(f"[CLICK - ERROR] tried to click but an error occured: {e}")
        raise


@register("fill")
def handle_fill(cmd):
    children = cmd.children[0]
    variable = children.children[0]

    defined_locator = resolve_selector(variable, "[FILL - ERROR]")
    valid_fills = {"tag": {"input", "textarea"},
                   "type": {"text", "email", "password", "search", "url", "''"}}
    locator, _ = get_locator(defined_locator, "[FILL - ERROR]")
    entered_text = children.children[1].value.strip('"')
    text = resolve_prefix(entered_text, "[FILL - ERROR]")

    tag = locator.evaluate("element => element.tagName.toLowerCase()")

    if tag in valid_fills["tag"] and (tag == "input" and locator.get_attribute("type") in valid_fills["type"]) or tag == "textarea":
        print(f"[FILL] {variable} [WITH] '{text}'")
        locator.fill(text)

@register("check_page")
def handle_check_page(cmd):
    page_name = " ".join(token.value for token in cmd.children[0].children if isinstance(token, Token) and token.type == "NAME")
    rows = cmd.children[0].children[1].children
    entered_locators = {row.value.strip() for row in rows}

    verified_locators = resolve_selectors(entered_locators, "[VERIFY-PAGE - ERROR]")
    
    assert_all_unique_and_visible(verified_locators, "[VERIFY-PAGE - ERROR]")

    print(f"[VERIFY-PAGE] {page_name} page loaded correctly")

@register("element_visible")
def handle_element_visible(cmd):
    children = cmd.children[0]
    variable = children.children[0].value.strip()
    present_or_not = children.children[1].value.strip()
    
    defined_locator = resolve_selector(variable, "[ELEMENT-VISIBLE - ERROR]")
    _, element_is_visible = get_locator(defined_locator, "[ELEMENT-VISIBLE - ERROR]")

    if present_or_not == "is":
        if not element_is_visible:
            raise Exception(f"[ELEMENT-VISIBLE - ERROR] element {variable} is not visible")
        print(f"[ELEMENT-VISIBLE] element {variable} is visible in page")
    else:
        if element_is_visible:
            raise Exception(f"[ELEMENT-VISIBLE - ERROR] element {variable} is visible but shouldn't be")
        print(f"[ELEMENT-VISIBLE] element {variable} is not visible in page")

@register("define_locator")
def handle_define(cmd):
    children = cmd.children[0]
    defined_locator = children.children[1].value.strip()
    variable = children.children[0].value.strip()
    if variable in ctx.locator_map:
        print(f"[MERGE-ALERT] merging already defined locators, {variable} locator was already defined")
    ctx.locator_map[variable] = defined_locator

@register("fill_form")
def handle_fill_form(cmd):
    rows = cmd.children[0].children
    variable_locators = {token.value.strip() for token in rows if isinstance(token, Token) and token.type == "NAME"}
    resolve_selectors(variable_locators, "[FILL-FORM - ERROR]")

    for i in range(0, len(rows), 2):
        locator_variable_name = rows[i].value.strip()
        entered_locator = resolve_selector(locator_variable_name, "[FILL-FORM - ERROR]")
        entered_text = rows[i + 1].value.strip('"')
        text = resolve_prefix(entered_text, "[FILL-FORM - ERROR]")

        page_locator, _ = get_locator(entered_locator, "[FILL-FORM - ERROR]")

        valid_fills = { "tag": {"input", "textarea"},
                        "type": {"text", "email", "password", "search", "url", "''"}}

        tag = page_locator.evaluate("element => element.tagName.toLowerCase()")
        if not (tag in valid_fills["tag"] and (tag == "input" and page_locator.get_attribute("type") in valid_fills["type"]) or tag == "textarea"):
            raise Exception(f"[FILL-FORM - ERROR] locator '{locator_variable_name}' is not fillable with data")

        page_locator.fill(text) 

    print(f"[FILL-FORM] form filled successfully")

@register("select_tag")
def handle_select(cmd):
    children = cmd.children[0]
    option_to_select = children.children[0].value.strip('"')
    locator_variable = children.children[1].value.strip()

    defined_locator = resolve_selector(locator_variable, "[SELECT - ERROR]")
    page_locator,_ = get_locator(defined_locator, "[SELECT - ERROR]")

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
def select_list_handler(cmd):
    rows = cmd.children[0].children
    variable_locators = {token.value.strip() for token in rows if isinstance(token, Token) and token.type == "NAME"}
    resolve_selectors(variable_locators, "[SELECT-LIST - ERROR]")

    for i in range(0, len(rows), 2):
        entered_variable_name = rows[i].value.strip()
        solved_locator = resolve_selector(entered_variable_name, "[SELECT-LIST - ERROR]")
        option_to_select = rows[i + 1].value.strip('"')
        defined_locator,_ = get_locator(solved_locator, "[SELECT-LIST - ERROR]")

        tag = defined_locator.evaluate("element => element.tagName.toLowerCase()") == "select"
        if not tag:
            raise Exception(f"[SELECT-LIST - ERROR] element {entered_variable_name} is not a select element")

        try:
            defined_locator.select_option(label=option_to_select)
        except Exception as e:
            print(f"[SELECT-LIST - ERROR] something happened when selecting option {entered_variable_name}, error: {e}")

    print(f"[SELECT-LIST] all options selected")

@register("checkbox_check")
def check_uncheck_handler(cmd):
    children = cmd.children[0]
    action = children.children[0].value.strip()
    entered_locator = children.children[1].value.strip()
    label = "[CHECK]" if action == "check" else "[UNCHECK]"
    label_error = "[CHECK - ERROR]" if action == "check" else "[UNCHECK - ERROR]"

    valid_checks = {"tag": "input",
                    "type": {"checkbox", "radio"}}

    defined_locator = resolve_selector(entered_locator, label_error)
    page_locator,_= get_locator(defined_locator, label_error)

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
def handle_text_visible(cmd):
    children = cmd.children[0]
    entered_text = children.children[1].value.strip('"')
    text = resolve_prefix(entered_text, "[CHECK-TEXT - ERROR]", mocked_true=False)
    entered_tag = children.children[2].value.strip("<>")
    present_in_page = children.children[3].value.strip('"')
    text_to_look = f"//{entered_tag}[contains(text(), '{text}')]"
    _, text_is_visible = get_locator(text_to_look, "[CHECK-TEXT - ERROR]")

    if present_in_page == "is":
        if not text_is_visible:
            raise Exception(f"[CHECK-TEXT - ERROR] text '{text}' is not visible")
        print(f"[CHECK-TEXT] text '{text}' is visible in page")
    else:
        if text_is_visible:
            raise Exception(f"[CHECK-TEXT - ERROR] text '{text}' is visible but shouldn't be")
        print(f"[CHECK-TEXT] text '{text}' is not visible in page")

@register("import_locators")
def handle_import_locators(cmd):
    filename = cmd.children[0].children[0].value.strip()
    locators_path = Path(f"tests/locators/{filename}.yaml")

    if not locators_path.exists():
        raise FileNotFoundError(f"[IMPORT-LOCATORS] failed, file not found: {locators_path}, file should be [filename].yaml inside a 'locators' folder inside tests folder")

    with open(locators_path, "r", encoding="utf-8") as f:
        locators = yaml.safe_load(f)

        if not isinstance(locators, dict):
            raise ValueError("[IMPORT-LOCATORS] YAML format invalid (must be key-value)")

        ctx.locator_map.update(locators)

@register("use_function")
def handle_define_function(cmd):
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
        command_handlers[decorator_name](command)

@register("save_variable")
def handle_save_variable(cmd):
    children = cmd.children[0].children
    children_len = len(children)
    to_save_in_variable = children[0].value.strip('"')
    entered_variable_name = children[1].value.strip() if children_len == 2 else children[2].value.strip()
    index = None if children_len == 2 else int(children[1])
    to_save_in_variable = resolve_prefix(to_save_in_variable, "[SAVE-VARIABLE - ERROR]", var_true=False, index=index)

    ctx.variables[entered_variable_name] = to_save_in_variable

@register("upload_file")
def handle_upload_file(cmd):
    children = cmd.children[0]
    entered_file_name = children.children[0].value.strip('"')
    locator_variable = resolve_selector(children.children[1].value.strip(), "[UPLOAD-FILE]")
    file_path = Path(f"tests/files/{entered_file_name}")

    if not file_path.exists():
        raise Exception(f"[UPLOAD-FILE] error, file '{entered_file_name}' not found")

    page_locator,_ = get_locator(locator_variable, "[UPLOAD-FILE]")
    tag = page_locator.evaluate("element => element.tagName.toLowerCase()")

    if tag != "input" or page_locator.get_attribute("type") != "file":
        raise Exception(f"[UPLOAD-FILE] failed, element is not an input or is an input but not type file")

    page_locator.set_input_files(file_path)

#FIXME
# @register("accept_dismiss")
# def handle_accept_dismiss(cmd, page):
#     print(cmd)

@register("wait")
def handle_wait(cmd):
    seconds_to_wait = cmd.children[0].children[0].value
    time.sleep(int(seconds_to_wait))
    print(f"[WAIT] waited for {seconds_to_wait} seconds")

@register("assert_match")
def handle_assert_match(cmd):
    children = cmd.children[0].children
    pair = []
    i = 0
    if len(children) > 2:
        while i < len(children):
            if children[i].type == "COMPLEX_VALUE":
                value = children[i].value.strip('"')
                number = children[i + 1] if i + 1 < len(children) and children[i + 1].type == "INT" else None
                value_solved = resolve_prefix(value, "[ASSERT - ERROR]", mocked_true=False, index=number)
                i += 2 if number else 1
                pair.append(value_solved)
            else:
                i += 1

        print(f"[ASSERT] '{pair[0]}' matches with '{pair[1]}'")
    else:
        maybe_num = lambda s: int(s) if s.isdigit() else s
        has_variable_or_txt = lambda entered_value: resolve_prefix(entered_value, "[ASSERT - ERROR]", mocked_true=False)

        first_value = maybe_num(has_variable_or_txt(children[0].value.strip('"')))
        second_value = maybe_num(has_variable_or_txt(children[1].value.strip('"')))

        if not first_value == second_value:
            raise Exception(f"[ASSERT - ERROR] '{first_value}' is different that '{second_value}'")

        print(f"[ASSERT] '{first_value}' matches with '{second_value}'")
