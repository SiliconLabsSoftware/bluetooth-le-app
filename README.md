# Bluetooth LE Application Examples

This repository is the **application project layer** of the [Silicon Labs Bluetooth Low Energy SDK](https://www.silabs.com/software-and-tools/bluetooth-low-energy). It provides a public contribution interface for Bluetooth LE example application projects that ship with the Simplicity SDK.

It is an early step toward [open development of the Simplicity SDK](https://www.silabs.com/software-and-tools/simplicity-software-development-kit): you continue to download and develop with the Simplicity SDK as usual, and use this repository when you want to share a bug fix or feature with the community.

## What is in this repository

- Example application projects under [`example/`](example/) and [`example_host/`](example_host/)
- Shared application code under [`common/`](common/)
- Related bootloader and packaging assets used by those examples

Day-to-day development, builds, and flashing still happen through the Simplicity SDK and [Simplicity Studio](https://www.silabs.com/developers/simplicity-studio) (or your usual toolchain). This repository is where community contributions to those example projects are proposed and reviewed.

## Generated files

Some files that appear in a full Simplicity SDK install are **not** shipped in this git repository. In particular, the ESL Access Point (ESL AP) host example depends on generated Python wrappers that are produced at build time rather than checked in.

To generate those wrappers:

1. Ensure [Python](https://www.python.org/) is installed.
2. Navigate to [`example_host/bt_host_esl_ap`](example_host/bt_host_esl_ap).
3. Run `make`.

## Getting started

1. Install and develop with the [Simplicity SDK](https://www.silabs.com/software-and-tools/simplicity-software-development-kit) as you normally do.
2. Work on the Bluetooth LE example that matches your use case until you have a change worth sharing (bug fix or feature).
3. Use the contribution flow below to propose that change back to Silicon Labs and the community.

Your Simplicity SDK version must match the version of this repository that you contribute against. Check the package version in [`bluetooth_le_app.slsdk`](bluetooth_le_app.slsdk), or use the git tag or release that corresponds to your installed Simplicity SDK.

For product documentation, stack features, and release notes, see the [Bluetooth Low Energy SDK](https://www.silabs.com/software-and-tools/bluetooth-low-energy) page and the [Silicon Labs documentation site](https://docs.silabs.com/bluetooth/latest/bluetooth-start/).

## Contributing

Contributions that improve Bluetooth LE example applications are welcome. Before opening a pull request, please review the [contributing guidelines](CONTRIBUTING.md), the [Contributor License Agreement](https://github.com/SiliconLabsSoftware/agreements-and-guidelines/blob/main/contributor_license_agreement.md), and the [Code of Conduct](CODE_OF_CONDUCT.md).

### Contribution flow

1. Download and develop with the Simplicity SDK as you normally do. Use a Simplicity SDK version that matches the git repository version you will contribute to.
2. If you have a change (bug fix or feature) that you want to share with the community, fork and clone this repository. Check out the branch or tag that matches your Simplicity SDK version.
3. Find the matching project in this repository (typically under [`example/`](example/) or [`example_host/`](example_host/)).
4. Copy your changes from the project you worked on into the corresponding files in your clone.
5. Create a new branch and open a **draft** pull request against the matching version branch.
6. Wait for the automatic workflows on the draft PR to pass. Fix any failures, then mark the pull request as ready for review and address feedback.

Start with a draft PR so you can confirm CI passes before requesting review. Pull requests should describe the problem or feature, the changes made, and how they were verified. Use the repository pull request template when opening a PR.

## License

See [LICENSE.md](LICENSE.md) for details.
