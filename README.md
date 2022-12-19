# flake8-error-link

Have you ever encountered an error when using a package and then gone to Google
to find out how to solve the error? Wouldn't your users prefer to go directly
to your documentation that tells them exactly what went wrong and how to
resolve that error? `flake8-error-link` checks the way excpetions are raised in
your code base to ensure that a link with more information is provided.

## Getting Started

```shell
python -m venv venv
source ./venv/bin/activate
pip install flake8 flake8-error-link
flake8 source.py
```

On the following code:

```Python
# source.py
raise Exception
```

This will produce warnings such as:

```shell
source.py:1:0: ELI001 builtin exceptions should be raised with a link to more information: https://github.com/jdkandersson/flake8-error-link
```

This can be resolved by changing the code to:

```Python
# source.py
raise Exception("more information: https://github.com/jdkandersson/flake8-error-link")
```

## Configuration

The plugin adds the following configurations to `flake8`:

* `--error-link-regex`: The regular expression to use to verify the way
  exceptions are reased, defaults to
  `more information: (mailto\:|(news|(ht|f)tp(s?))\:\/\/){1}\S+`


## Rules

* `ELI001`: checks that any builtin exceptions that are raised with constant
   arguments include a link to more information.
* `ELI002`: checks that any custom exceptions that are raised with constant
   arguments include a link to more information.
