# Contributing to pypm

First off, thank you for considering contributing to pypm! It's people like you that make pypm such a great tool.

## 🤝 How to Contribute

### Reporting Bugs

This section guides you through submitting a bug report for pypm. Following these guidelines helps maintainers and the community understand your report, reproduce the behavior, and find related reports.

- **Use a clear and descriptive title** for the issue to identify the problem.
- **Describe the exact steps which reproduce the problem** in as many details as possible.
- **Provide specific examples to demonstrate the steps**. Include links to files or GitHub projects, or copy/pasteable snippets, which you use in those examples.

### Suggesting Enhancements

This section guides you through submitting an enhancement suggestion for pypm, including completely new features and minor improvements to existing functionality.

- **Use a clear and descriptive title** for the issue to identify the suggestion.
- **Provide a step-by-step description of the suggested enhancement** in as many details as possible.
- **Explain why this enhancement would be useful** to most pypm users.

### Pull Requests

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.

## 💻 Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Suriyakumardurai/pypm.git
   cd pypm
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .[dev]
   ```

4. **Run tests**
   ```bash
   pytest
   ```

5. **Lint and Type Check**
   ```bash
   ruff check .
   mypy src/pypm
   ```

6. **Performance Testing**
   If you are modifying the scanner or parser, please ensure no performance regressions.
   ```bash
   pypm infer --bench
   ```

## 🎨 Code Style

- We use `ruff` for linting and formatting.
- we use `mypy` for static type checking.
- Please enable type checking and linting in your editor to catch issues early.

## 📜 License

By contributing, you agree that your contributions will be licensed under its MIT License.
