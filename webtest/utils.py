from faker import Faker
import re

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
