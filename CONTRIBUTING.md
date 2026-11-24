# Contributing

1. Create a virtual environment and install the project with `pip install -e .`.
2. Run `python -m unittest discover -v` before submitting changes.
3. Run the offscreen Qt test command from the README.
4. Do not commit `.env`, databases, screenshots, or credentials.
5. Keep database changes in numbered migrations and preserve existing user data.

Please open an issue before large architectural changes. Include the operating
system, Python version, reproduction steps, and relevant sanitized logs.
