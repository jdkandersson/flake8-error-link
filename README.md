# flake8-error-link

Have you ever encountered an error when using a package and then gone to Google
to find out how to solve the error? Wouldn't your users prefer to go directly
to your documentation that tells them exactly what went wrong and how to
resolve that error? `flake8-error-link` checks the way exceptions are raised in
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

A few rules have been defined to allow for selective suppression:

* `ELI001`: checks that any builtin exceptions that are raised with constant
   arguments include a link to more information.
* `ELI002`: checks that any custom exceptions that are raised with constant
   arguments include a link to more information.
* `ELI003`: checks that any exceptions that are raised with variable arguments
  include a constant argument with a link to more information.
* `ELI004`: checks that any exceptions that are re-raised include a constant
  argument with a link to more information.

### Fix ELI001

This linting rule is trigger by raising an inbuilt exception without providing
a constant that include a link to more information as one of the arguments to
the constructor. For example:

```Python
raise Exception

raise ValueError

raise Exception()

raise Exception("something went wrong")
```

These examples can be fixed by using something like:

```Python
raise Exception(
    "more information: https://github.com/jdkandersson/flake8-error-link"
)

raise ValueError(
    "more information: https://github.com/jdkandersson/flake8-error-link"
)

raise Exception(
    "more information: https://github.com/jdkandersson/flake8-error-link"
)

raise Exception(
    "something went wrong",
    "more information: https://github.com/jdkandersson/flake8-error-link",
)
```

### Fix ELI002

This linting rule is trigger by raising a custom exception without providing
a constant that include a link to more information as one of the arguments to
the constructor. For example:

```Python
class CustomError(Exception):
    pass

raise CustomError

raise CustomError()

raise CustomError("something went wrong")
```

These examples can be fixed by using something like:

```Python
class CustomError(Exception):
    pass

raise CustomError(
    "more information: https://github.com/jdkandersson/flake8-error-link"
)

raise CustomError(
    "more information: https://github.com/jdkandersson/flake8-error-link"
)

raise CustomError(
    "something went wrong",
    "more information: https://github.com/jdkandersson/flake8-error-link",
)
```

### Fix ELI003

This linting rule is trigger by raising an exception and passing at least one
argument without providing a constant that include a link to more information
as one of the arguments to the constructor. For example:

```Python
message = "something went wrong"

def get_message():
    return message

raise Exception(get_message())

raise Exception(f"{message} quite badly")
```

These examples can be fixed by using something like:

```Python
message = "something went wrong"

def get_message():
    return message

raise Exception(
    get_message(),
    "more information: https://github.com/jdkandersson/flake8-error-link",
)

raise Exception(
    f"{message} quite badly, more information: https://github.com/jdkandersson/flake8-error-link"
)
```

### Fix ELI004

This linting rule is trigger by re-raising an exception. For example:

```Python
try:
    raise Exception(
        "more information: https://github.com/jdkandersson/flake8-error-link"
    )
except Exception:
    raise
```

This example can be fixed by using something like:

```Python
try:
    raise Exception(
        "more information: https://github.com/jdkandersson/flake8-error-link"
    )
except Exception as exc:
    raise Exception(
        "more information: https://github.com/jdkandersson/flake8-error-link"
    ) from exc
```
