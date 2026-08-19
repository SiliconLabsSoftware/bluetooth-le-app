# Resolve package root and fallback to simplicity-sdk subfolder if not found. Normalize paths to Unix style.
package_path = $(subst \,/,$(if $(shell slt where $(1)),$(shell slt where $(1)),$(shell slt where simplicity-sdk)/$(1)))

.DEFAULT_GOAL := all

# Resolve include paths
PLATFORM_COMMON_INC_PATH := $(call package_path,platform_core)/platform/common/inc
PLATFORM_MBEDTLS_INC_PATH := $(call package_path,mbedtls)/include
BT_HOST_INC_PATH := $(call package_path,bluetooth_le_host)/inc
BGAPI_PROTOCOL_PATH := $(call package_path,bgapi_protocol)
BLUETOOTH_LE_MIDDLEWARE_PATH := $(call package_path,bluetooth_le_middleware)

# Derived paths
BGAPI_PROTOCOL_INC_PATH := $(BGAPI_PROTOCOL_PATH)/protocol/inc
BGAPI_CONFIG_PATH := $(BGAPI_PROTOCOL_PATH)/config
OTF_COMPRESSOR_CONFIG_PATH := $(BLUETOOTH_LE_MIDDLEWARE_PATH)/common/otf_decompressor/otf_compressor_config.h
EAD_CORE_INC_PATH := $(BLUETOOTH_LE_MIDDLEWARE_PATH)/common/ead_core
ESL_TAG_CORE_INC_PATH := $(BLUETOOTH_LE_MIDDLEWARE_PATH)/common/esl_tag_core/inc
ESL_TAG_CORE_CONFIG_PATH := $(BLUETOOTH_LE_MIDDLEWARE_PATH)/common/esl_tag_core/config

# Common headers used by both wrappers
COMMON_HEADERS = \
    $(PLATFORM_COMMON_INC_PATH)/sl_status.h \
    $(BGAPI_PROTOCOL_INC_PATH)/sl_bgapi.h \
    $(BGAPI_CONFIG_PATH)/sl_bgapi_config.h \
    $(EAD_CORE_INC_PATH)/sl_bt_ead_core.h \
    $(ESL_TAG_CORE_INC_PATH)/esl_tag_core.h \
    $(ESL_TAG_CORE_CONFIG_PATH)/esl_tag_core_config.h

# Common include dirs
COMMON_INCLUDE_DIRS = $(sort $(dir $(COMMON_HEADERS)))
COMMON_INCLUDE_FLAGS = $(addprefix -I,$(COMMON_INCLUDE_DIRS))

.PHONY: all clean help esl_lib_wrapper esl_key_lib_wrapper

VENV_DIR := .venv
PYTHON := python3
ifeq ($(OS),Windows_NT)
    VENV_PYTHON := $(VENV_DIR)/Scripts/python.exe
    VENV_CTYPESGEN := $(VENV_DIR)/Scripts/ctypesgen.exe
else
    VENV_PYTHON := $(VENV_DIR)/bin/python3
    VENV_CTYPESGEN := $(VENV_DIR)/bin/ctypesgen
endif

# Try system ctypesgen first
SYSTEM_CTYPESGEN := $(shell which ctypesgen 2>/dev/null)
ifeq ($(SYSTEM_CTYPESGEN),)
CTYPESGEN := $(VENV_CTYPESGEN)
else
CTYPESGEN := $(SYSTEM_CTYPESGEN)
endif
# ---------------------------------------------------------------------------
# esl_lib_wrapper.py
# ---------------------------------------------------------------------------

# Primary dependencies of esl_lib wrapper
PRIMARY_ESL_LIB_DEPS = \
    esl_lib/esl_lib.h \
    esl_lib/esl_lib_adv_dedup_config.h \
    $(PLATFORM_COMMON_INC_PATH)/sl_status.h \
    $(OTF_COMPRESSOR_CONFIG_PATH)

# Secondary dependencies of esl_lib wrapper
SECONDARY_ESL_LIB_DEPS = $(COMMON_HEADERS)

# All dependencies
ESL_LIB_DEPS = $(PRIMARY_ESL_LIB_DEPS) $(SECONDARY_ESL_LIB_DEPS)

# Include dirs and flags
ESL_LIB_INCLUDE_DIRS = $(sort $(dir $(ESL_LIB_DEPS)))
ESL_LIB_INCLUDE_FLAGS = $(addprefix -I,$(ESL_LIB_INCLUDE_DIRS))

# ctypesgen inputs
CTYPESGEN_ESL_LIB = $(PRIMARY_ESL_LIB_DEPS)

# Target rule
esl_lib_wrapper.py: $(ESL_LIB_DEPS)
	@echo "Generating $@..."
	$(CTYPESGEN) --no-gnu-types --allow-gnu-c --no-macro-warnings \
		--runtime-libdir ./lib \
		$(ESL_LIB_INCLUDE_FLAGS) \
		$(CTYPESGEN_ESL_LIB) \
		-x sl_status_get_string_n -x sl_status_print \
		-o $@ 2> /dev/null
	$(PYTHON) ctypesgen_wrapper_fix.py $@

# ---------------------------------------------------------------------------
# esl_key_lib_wrapper.py
# ---------------------------------------------------------------------------

# Primary dependencies of esl_key_lib wrapper
PRIMARY_KEY_LIB_DEPS = \
    ./esl_key_lib/esl_key_lib.h \
    $(PLATFORM_COMMON_INC_PATH)/sl_status.h

# Secondary dependencies of esl_key_lib wrapper
SECONDARY_KEY_LIB_DEPS = \
    $(COMMON_HEADERS) \
    $(BT_HOST_INC_PATH)/sl_bt_api.h \
    $(PLATFORM_MBEDTLS_INC_PATH)/psa/crypto_types.h

# All dependencies
KEY_LIB_DEPS = $(PRIMARY_KEY_LIB_DEPS) $(SECONDARY_KEY_LIB_DEPS)

# Include dirs and flags
KEY_LIB_INCLUDE_DIRS = $(sort $(dir $(KEY_LIB_DEPS)))
KEY_LIB_INCLUDE_FLAGS = $(addprefix -I,$(KEY_LIB_INCLUDE_DIRS))

# ctypesgen inputs
CTYPESGEN_KEY_LIB = $(PRIMARY_KEY_LIB_DEPS)

# Target rule
esl_key_lib_wrapper.py: $(KEY_LIB_DEPS)
	@echo "Generating $@..."
	$(CTYPESGEN) --no-gnu-types --no-macro-warnings \
		--runtime-libdir ./lib \
		$(KEY_LIB_INCLUDE_FLAGS) \
		-I$(PLATFORM_MBEDTLS_INC_PATH) \
		$(CTYPESGEN_KEY_LIB) \
		-o $@ 2> /dev/null
	$(PYTHON) ctypesgen_wrapper_fix.py $@

$(VENV_CTYPESGEN):
	@echo "System ctypesgen not found, installing into venv..."
	$(PYTHON) -m venv $(VENV_DIR); \
	$(VENV_PYTHON) -m ensurepip --upgrade; \
	$(VENV_PYTHON) -m pip install --upgrade pip; \
	$(VENV_PYTHON) -m pip install ctypesgen

# ---------------------------------------------------------------------------
# Phony targets
# ---------------------------------------------------------------------------
all: esl_lib_wrapper esl_key_lib_wrapper

esl_lib_wrapper: $(CTYPESGEN) esl_lib_wrapper.py

esl_key_lib_wrapper: $(CTYPESGEN) esl_key_lib_wrapper.py

clean:
	@echo "Cleaning generated files..."
	rm -f esl_lib_wrapper.py esl_key_lib_wrapper.py

help:
	@echo "Available targets:"
	@echo ""
	@echo "  all                     Build both wrappers"
	@echo "  esl_lib_wrapper         Generate ESL library Python wrapper"
	@echo "  esl_key_lib_wrapper     Generate ESL key library Python wrapper"
	@echo "  clean                   Remove generated wrapper files"
	@echo "  help                    Show this help message"
