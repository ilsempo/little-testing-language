from faker import Faker
import re
from playwright.sync_api import TimeoutError as PWTimeoutError
from webtest.context import ctx

def generate_mocked_data(entered_text):
    fake = Faker('es_AR')
    mocked_type = {
        "name": fake.name().split(" ")[0],
        "surname": fake.name().split(" ")[1],
        "email": fake.email(),
        "address": fake.address().split(",")[0],
        "phone": fake.phone_number(),
        "company": fake.company(),
        "password": fake.password(length=8, special_chars=True, digits=True, upper_case=True, lower_case=True),
        "zipcode": fake.postcode(),
        "sentence": fake.sentence(nb_words=6),
        "text": fake.text(max_nb_chars=200)
    }
    type = entered_text.split(":")[1]
    mocked_data = mocked_type[type]
    return mocked_data

def load_functions(path):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    functions = {}

    pattern = r'MACRO (\w+):\n(.*?)\nEND MACRO'
    matches = re.findall(pattern, content, re.DOTALL)

    for name, body in matches:
        functions[name] = body.strip()

    return functions

def resolve_selector(entered_locator, label_error):
    if entered_locator not in ctx.locator_map:
        raise Exception(f"{label_error} undefined locator: {entered_locator}")
    return ctx.locator_map[entered_locator]

def resolve_selectors(entered_locators, label_error):
    missing = {loc for loc in entered_locators if loc not in ctx.locator_map}
    if missing:
        raise Exception(f"{label_error} undefined locators: {missing}")
    return {loc: ctx.locator_map[loc] for loc in entered_locators}

def get_unique_locator(page, selector, label_error, require_visible=True, require_clickable=False, timeout_ms=5000):
    loc = page.locator(selector)
    try:
        loc.first.wait_for(state="attached", timeout=timeout_ms)
    except PWTimeoutError:
        if loc.count() == 0:
            raise Exception(f"{label_error} locator '{selector}' does not match any element")

    count = loc.count()
    if count == 0:
        raise Exception(f"{label_error} locator '{selector}' does not match any element")
    if count > 1:
        raise Exception(f"{label_error} locator '{selector}' matches more than one element, please define a more specific locator")

    if require_visible:
        is_visible = False
        try:
            loc.wait_for(state="visible", timeout=timeout_ms)
            is_visible = True
        except PWTimeoutError:
            if not loc.is_visible():
                raise Exception(f"{label_error} locator found but not visible: '{selector}'")
        if require_clickable:
            pointer_events = loc.evaluate("el => getComputedStyle(el).pointerEvents")
            if pointer_events == "none":
                raise Exception(f"{label_error} locator '{selector}' is not clickable (pointer-events: none)")

    return loc, is_visible

def assert_all_unique_and_visible(page, selectors_dict, label_error, timeout_ms=5000):
    errors = []
    result = {}
    for name, selector in selectors_dict.items():
        try:
            result[name] = get_unique_locator(page, selector, label_error, require_visible=True, timeout_ms=timeout_ms)
        except Exception as e:
            errors.append(f"{name} -> {e}")
    if errors:
        raise Exception(f"{label_error} locator issues:\n- " + "\n- ".join(errors))
    return result