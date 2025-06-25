MININET = mininet/*.py
TEST = mininet/test/*.py
EXAMPLES = mininet/examples/*.py
MN = bin/mn
PYTHON ?= python
PYMN = $(PYTHON) -B bin/mn
BIN = $(MN)
PYSRC = $(MININET) $(TEST) $(EXAMPLES) $(BIN)
MNEXEC = mnexec
MANPAGES = mn.1 mnexec.1
P8IGN = E251,E201,E302,E202,E126,E127,E203,E226,E402,W504,W503,E731
PREFIX ?= /usr
BINDIR ?= $(PREFIX)/bin
MANDIR ?= $(PREFIX)/share/man/man1
DOCDIRS = doc/html doc/latex
PDF = doc/latex/refman.pdf
CC ?= cc
CFLAGS += -Wall -Wextra

# Check if we're in a virtual environment or if --break-system-packages is needed
VENV_ACTIVE := $(shell $(PYTHON) -c "import sys; print('1' if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else '0')")
PIP_VERSION := $(shell pip --version 2>/dev/null | cut -d' ' -f2 | cut -d'.' -f1)
PIP_MAJOR := $(shell echo $(PIP_VERSION) | head -c1)

# Determine pip install flags based on environment
ifeq ($(VENV_ACTIVE),1)
    # In virtual environment, no special flags needed
    PIP_INSTALL_FLAGS := 
    PIP_UNINSTALL_FLAGS := 
else
    # Not in virtual environment, check pip version
    ifeq ($(shell test $(PIP_MAJOR) -ge 23 && echo 1),1)
        # pip >= 23.0, use --break-system-packages
        PIP_INSTALL_FLAGS := --break-system-packages
        PIP_UNINSTALL_FLAGS := --break-system-packages
    else
        # Older pip version, try --user as fallback
        PIP_INSTALL_FLAGS := --user
        PIP_UNINSTALL_FLAGS := 
    endif
endif

all: codecheck test

clean:
	rm -rf build dist *.egg-info *.pyc $(MNEXEC) $(MANPAGES) $(DOCDIRS)

codecheck: $(PYSRC)
	-echo "Running code check"
	util/versioncheck.py
	pyflakes3 $(PYSRC) || pyflakes $(PYSRC)
	pylint --rcfile=.pylint $(PYSRC)
#	Exclude miniedit from pep8 checking for now
	pep8 --repeat --ignore=$(P8IGN) `ls $(PYSRC) | grep -v miniedit.py`

errcheck: $(PYSRC)
	-echo "Running check for errors only"
	pyflakes3 $(PYSRC) || pyflakes $(PYSRC)
	pylint -E --rcfile=.pylint $(PYSRC)

test: $(MININET) $(TEST)
	-echo "Running tests"
	mininet/test/test_nets.py
	mininet/test/test_hifi.py

slowtest: $(MININET)
	-echo "Running slower tests (walkthrough, examples)"
	mininet/test/test_walkthrough.py -v
	mininet/examples/test/runner.py -v

mnexec: mnexec.c $(MN) mininet/net.py
	$(CC) $(CFLAGS) $(LDFLAGS) \
	-DVERSION=\"`PYTHONPATH=. $(PYMN) --version 2>&1`\" $< -o $@

install-mnexec: $(MNEXEC)
	install -D $(MNEXEC) $(BINDIR)/$(MNEXEC)

install-manpages: $(MANPAGES)
	install -D -t $(MANDIR) $(MANPAGES)

# Enhanced install target with better environment detection
install: install-mnexec install-manpages
	@echo "Detected environment: VENV_ACTIVE=$(VENV_ACTIVE), PIP_VERSION=$(PIP_VERSION)"
	@echo "Using pip flags: install=$(PIP_INSTALL_FLAGS), uninstall=$(PIP_UNINSTALL_FLAGS)"
	pip uninstall -y mininet $(PIP_UNINSTALL_FLAGS) || true
	pip install . $(PIP_INSTALL_FLAGS)

# Alternative install targets for specific scenarios
install-venv: install-mnexec install-manpages
	@echo "Installing in virtual environment (no special flags)"
	pip uninstall -y mininet || true
	pip install .

install-system: install-mnexec install-manpages
	@echo "Installing system-wide with --break-system-packages"
	pip uninstall -y mininet --break-system-packages || true
	pip install . --break-system-packages

install-user: install-mnexec install-manpages
	@echo "Installing for current user only"
	pip uninstall -y mininet || true
	pip install . --user

develop: $(MNEXEC) $(MANPAGES)
# 	Perhaps we should link these as well
	install $(MNEXEC) $(BINDIR)
	install $(MANPAGES) $(MANDIR)
	$(PYTHON) -m pip uninstall -y mininet || true
	$(PYTHON) -m pip install -e . --no-binary :all: $(PIP_INSTALL_FLAGS)

man: $(MANPAGES)

mn.1: $(MN)
	PYTHONPATH=. help2man -N -n "create a Mininet network." \
	--no-discard-stderr "$(PYMN)" -o $@

mnexec.1: mnexec
	help2man -N -n "execution utility for Mininet." \
	-h "-h" -v "-v" --no-discard-stderr ./$< -o $@

.PHONY: doc
doc: man
	doxygen doc/doxygen.cfg
	make -C doc/latex

# Help target to explain the different install options
help:
	@echo "Mininet Makefile targets:"
	@echo "  all          - Run codecheck and test"
	@echo "  install      - Auto-detect environment and install appropriately"
	@echo "  install-venv - Install in virtual environment (recommended)"
	@echo "  install-system - Force system install with --break-system-packages"
	@echo "  install-user - Install for current user only (--user)"
	@echo "  develop      - Install in development mode"
	@echo "  test         - Run basic tests"
	@echo "  slowtest     - Run comprehensive tests"
	@echo "  clean        - Clean build artifacts"
	@echo "  help         - Show this help message"