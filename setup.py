from setuptools import setup

setup(
    name='webtest-runner',
    version='0.1',
    packages=['webtest', 'webtest.commands'],
    install_requires=[
        'playwright',
        'lark',
    ],
    entry_points={
        'console_scripts': [
            'webtest=webtest.runner:cli_entry',
        ],
    },
)