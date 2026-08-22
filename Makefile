# feature-lifecycle-skill
#
# `lint` is the gate. `selftest` is what makes the gate worth having: a checker
# nobody has watched fail is indistinguishable from one that returns zero
# unconditionally, so every check in tools/lint.py has a mutation that proves it
# blocks — and the mutation asserts the rule id, because a check that passes
# behind a neighbour's finding is no better guarded than one nobody ran.

REPO       := $(CURDIR)
SKILL      := $(REPO)/skills/feature-lifecycle
LINT       := python3 $(REPO)/tools/lint.py

CLAUDE_DIR := $(HOME)/.claude/skills
CODEX_DIR  := $(HOME)/.codex/skills
AGY_DIR    := $(HOME)/.gemini/skills

.DEFAULT_GOAL := help

DOCS       := $(REPO)/docs
PAGES_PORT ?= 8000

.PHONY: help lint lint-strict selftest check link unlink status hooks pages

help:
	@echo "make lint          check the skill (blocks on P1/P2)"
	@echo "make lint-strict   also block on advisory P3 findings"
	@echo "make selftest      prove each check blocks, and names itself, when broken"
	@echo "make check         lint + selftest — the full gate"
	@echo ""
	@echo "make link          symlink the skill into claude / codex / agy"
	@echo "make unlink        remove only the links pointing at this repo"
	@echo "make status        show where the skill is currently linked"
	@echo "make hooks         install the pre-commit hook (lints the staged content)"
	@echo ""
	@echo "make pages         preview the docs/ site (PAGES_PORT=$(PAGES_PORT))"
	@echo ""
	@echo "repo               $(REPO)"

lint:
	@$(LINT)

lint-strict:
	@$(LINT) --strict

selftest:
	@$(LINT) --selftest

check: lint selftest

# GitHub Pages serves docs/ as static files on `main`; this only previews the same
# tree locally, so what you see here is what the published site is.
pages:
	@echo "serving $(DOCS) at http://localhost:$(PAGES_PORT)/ — ctrl-c to stop"
	@python3 -m http.server $(PAGES_PORT) --directory "$(DOCS)"

# $(1) = CLI skills directory. Only ever creates or removes a link named `feature-lifecycle`
# that points at this repo; a real path already sitting there is reported, never
# overwritten.
define do_link
t="$(1)"; d="$$t/feature-lifecycle"; p=$$(dirname "$$t"); \
if [ ! -d "$$p" ]; then echo "skip    $$t — $$p does not exist"; exit 0; fi; \
mkdir -p "$$t"; \
if [ -L "$$d" ]; then \
  if [ "$$(readlink "$$d")" = "$(SKILL)" ]; then echo "ok      $$d already linked"; \
  else echo "ERROR   $$d is a symlink to $$(readlink "$$d") — resolve it, then re-run"; exit 1; fi; \
elif [ -e "$$d" ]; then echo "ERROR   $$d exists and is not a link into this repo"; exit 1; \
else ln -sfn "$(SKILL)" "$$d"; echo "linked  $$d"; fi
endef

define do_unlink
t="$(1)"; d="$$t/feature-lifecycle"; \
if [ -L "$$d" ] && [ "$$(readlink "$$d")" = "$(SKILL)" ]; then rm "$$d"; echo "unlink  $$d"; \
elif [ -e "$$d" ]; then echo "skip    $$d — not a link into this repo"; \
else echo "skip    $$d — not present"; fi
endef

link:
	@$(call do_link,$(CLAUDE_DIR))
	@$(call do_link,$(CODEX_DIR))
	@$(call do_link,$(AGY_DIR))

unlink:
	@$(call do_unlink,$(CLAUDE_DIR))
	@$(call do_unlink,$(CODEX_DIR))
	@$(call do_unlink,$(AGY_DIR))

status:
	@echo "skill   $(SKILL)"
	@for t in "$(CLAUDE_DIR)" "$(CODEX_DIR)" "$(AGY_DIR)"; do \
	  d="$$t/feature-lifecycle"; \
	  if [ -L "$$d" ]; then echo "link    $$d -> $$(readlink "$$d")"; \
	  elif [ -e "$$d" ]; then echo "other   $$d exists and is not a symlink"; \
	  else echo "none    $$d"; fi; \
	done

# The hook lints the **staged** content, not the working tree. The two differ
# whenever a fix is left unstaged, and a hook that reads the wrong one both passes
# commits it should block and blocks commits it should pass. `git checkout-index`
# materialises the index into a scratch tree; the linter runs against that.
#
# An existing hook this target did not write is reported, never overwritten — the
# same rule `do_link` applies to a path already sitting where a link would go.
hooks:
	@d="$(REPO)/.git/hooks/pre-commit"; \
	if [ -e "$$d" ] && ! grep -q "installed by feature-lifecycle-skill" "$$d" 2>/dev/null; then \
	  echo "ERROR   $$d exists and was not installed by this target — move it, then re-run"; exit 1; \
	fi; \
	mkdir -p "$(REPO)/.git/hooks"; \
	printf '%s\n' \
	  '#!/bin/sh' \
	  '# installed by feature-lifecycle-skill: make hooks' \
	  '# Lints the staged content, never the working tree.' \
	  'set -e' \
	  '# an explicit template: bare `mktemp -d` ignores TMPDIR on BSD/macOS' \
	  'tmp=$$(mktemp -d "$${TMPDIR:-/tmp}/fl-lint.XXXXXX")' \
	  '# the scratch tree goes even when a step below dies under `set -e`' \
	  'trap "rm -rf \"$$tmp\"" EXIT INT TERM' \
	  'git checkout-index -a -f --prefix="$$tmp/"' \
	  '# the selftest only when the checker itself changed' \
	  'if git diff --cached --name-only | grep -q "^tools/"; then' \
	  '  goal=check' \
	  'else' \
	  '  goal=lint' \
	  'fi' \
	  'status=0' \
	  'make -C "$$tmp" --no-print-directory "$$goal" || status=$$?' \
	  'exit $$status' \
	  > "$$d"; \
	chmod +x "$$d"; \
	echo "installed $$d"
