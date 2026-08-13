# Security and Safety

## Reporting a security issue

Please avoid filing a public issue for a vulnerability that could allow arbitrary code execution, unsafe path handling, or unintended programming operations. Report it privately to the repository maintainer using GitHub's private vulnerability reporting feature when enabled.

## Execution model

HexHeist does not execute generated commands through a shell. It passes the AVRDUDE executable and each argument separately to `QProcess`.

The **Custom arguments** field is still an expert feature: values can alter AVRDUDE behavior and can perform destructive hardware operations even though they are not shell commands.

## Hardware safety

- Treat fuse and lock writes as high risk.
- Verify the selected target before flashing.
- Do not use `-F` casually to bypass a signature mismatch.
- Validate new programmer/target combinations on recoverable hardware.
- Keep exported logs private if local file paths or device serial identifiers are sensitive in your environment.
