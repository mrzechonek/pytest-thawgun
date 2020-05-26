from setuptools import find_packages, setup

# fmt: off
setup(
    name='pytest-thawgun',
    version='0.0.3',
    packages=find_packages(),
    url='https://github.com/mrzechonek/thawgun',
    license='Apache 2.0',
    author='Michał Lowas-Rzechonek',
    author_email='michal@rzechonek.net',
    description='Pytest plugin for time travel',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Testing",
        "Framework :: Pytest",
    ],
    python_requires='>= 3.6',
    setup_requires=[
        'pytest-runner',
    ],
    install_requires=[
        'async-generator',
        'freezegun',
        'pytest-asyncio',
    ],
    tests_require=[
        'coveralls',
        'pytest-cov',
        'aiohttp',
    ],
    entry_points={
        'pytest11': ['thawgun = pytest_thawgun.plugin']
    },
)
# fmt: on
