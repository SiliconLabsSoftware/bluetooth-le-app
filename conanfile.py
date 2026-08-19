import glob
import json
import os
from conan import ConanFile
from conan.tools.files import copy
import yaml

def resolve_pattern(pattern):
    """Resolve a glob pattern to a list of file paths."""
    files = [f for f in glob.glob(pattern, recursive=True) if os.path.isfile(f)]
    if not files:
        raise FileNotFoundError(f"No files found for pattern: {pattern}")
    return files

class bluetooth_le_appRecipe(ConanFile):
    # Attributes: https://docs.conan.io/2/reference/conanfile/attributes.html

    # Package reference
    slsdk_file = "bluetooth_le_app.slsdk"

    # Basic Conan metadata
    description = "Bluetooth LE Applications"
    license = "www.silabs.com/about-us/legal/master-software-license-agreement"
    author = "Silicon Laboratories Inc."
    url = "https://github.com/SiliconLabsSoftware/bluetooth-le-app"
    topics = ["silabs", "bluetooth", "application"]

    # Python module for .slc files parsing/expansion
    python_requires = "silabs_package_assistant/[~1]@silabs"

    # Other attributes
    revision_mode = "scm"

    # Custom SLT metadata
    # Dictionary to declare properties
    options = {
      "compatibleVersion": ["ANY"],
      "subPackage": [True, False],
      "releaseNotesUrl": ["ANY"],
      "packageType": ["ANY"],
      "sdkLtsTag": ["ANY"]
    }

    # Dictionary to define properties values.
    # Alternative is to set values in def configure(self) of recipe
    default_options = {
      "compatibleVersion": "ANY",
      "subPackage": False,
      "releaseNotesUrl": "",
      "packageType": "sdk",
      "sdkLtsTag": ""
    }

    def set_name(self):
        silabs_package_assistant = self.python_requires["silabs_package_assistant"].module
        if not self.name:
            self.name = silabs_package_assistant.get_name(os.path.join(self.recipe_folder, self.slsdk_file))

    def set_version(self):
        silabs_package_assistant = self.python_requires["silabs_package_assistant"].module

        if not self.version:
            self.version = silabs_package_assistant.get_version(os.path.join(self.recipe_folder, self.slsdk_file))
        # if not self.channel:
        #     self.channel = silabs_package_assistant.get_channel()
        if not self.user:
            self.user = silabs_package_assistant.get_user()

    def package_info(self):
        # SDK Packages
        self.buildenv_info.append_path("SLC_SDK_PACKAGE_PATH", self.package_folder)

    def package_id(self):
        # Completely clear all the info, resulting `package_id` will be the same
        self.info.clear()

    def _get_slc_file_index(self):
        """
        Map each .slcp/.slcw to the paths referenced for this package.
        """
        silabs_package_assistant = self.python_requires["silabs_package_assistant"].module
        index = {}
        for slc_file in glob.iglob('**/*.slc[pw]', recursive=True):
            files = silabs_package_assistant.list_files_in_slc_file(
                slc_file_path=slc_file,
                desired_packages=[self.name],
                desired_qualities=['production', 'evaluation', 'experimental', 'deprecated'],
                fail_on_missing_files=True
            )
            if files:
                index[slc_file] = files
        return index

    def export(self):
        slc_file_index = self._get_slc_file_index()
        out_path = os.path.join(self.export_folder, "slc_file_index.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(slc_file_index, f, indent=2)

    def package(self):
        silabs_package_assistant = self.python_requires["silabs_package_assistant"].module

        slc_file_index = self._get_slc_file_index()

        files_to_package = {self.slsdk_file}
        for paths in slc_file_index.values():
            files_to_package.update(paths)

        # Collect files that are not referenced by SLC project files
        if os.path.exists(f"{self.name}.yml"):
            copy(self, f"{self.name}.yml",
                 src=self.source_folder,
                 dst=self.package_metadata_folder)
            with open(f"{self.name}.yml", "r", encoding="utf-8") as file:
                yaml_data = yaml.safe_load(file)
            for pattern in yaml_data.get("extra_files", []):
                self.output.info(f"Collecting extra files: {pattern}")
                files_to_package.update(resolve_pattern(pattern))

        silabs_package_assistant.copy_files(files_to_package,
                                            self.source_folder,
                                            self.package_folder)

        # Collect metadata files from the optional metadata directory
        if os.path.isdir("metadata"):
            copy(self, "*",
                 src=os.path.join(self.source_folder, "metadata"),
                 dst=self.package_metadata_folder)

        # Generate metadata for introspection/debug/reporting
        silabs_package_assistant.generate_metadata(self, files_to_package)
