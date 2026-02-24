# Installation Verification Checklist

Run these commands to verify your installation:

## 1. File Structure Check
```bash
cd automaton-auditor
tree -L 2 src/
```

Expected output:
```
src/
├── agents/
│   ├── detectives/
│   ├── judges/
│   └── justice/
├── core/
│   ├── config.py
│   ├── graph.py
│   └── state.py
├── tools/
│   ├── ast_tools.py
│   ├── git_tools.py
│   ├── pdf_tools.py
│   └── security.py
├── utils/
│   ├── exceptions.py
│   ├── formatters.py
│   ├── logger.py
│   └── validators.py
└── main.py
```

## 2. Python Module Check
```bash
python -c "
from src.agents import RepoInvestigator, Prosecutor, ChiefJustice
from src.core import create_auditor_graph, get_config
from src.tools import GitAnalyzer, ASTAnalyzer, PDFAnalyzer
from src.utils import logger, SecurityValidator
print('✓ All modules import successfully')
"
```

## 3. Configuration Validation
```bash
python -c "
from src.core.config import load_config
config = load_config('.env')
print(f'✓ Configuration loaded')
print(f'  - LLM Model: {config.default_llm_model}')
print(f'  - Max Repo Size: {config.max_repo_size_mb}MB')
print(f'  - Allowed Domains: {config.get_allowed_domains()}')
"
```

## 4. Rubric Loading
```bash
python -c "
from src.core.config import load_rubric
rubric = load_rubric('rubric/week2_rubric.json')
print(f'✓ Rubric loaded: {rubric[\"rubric_metadata\"][\"rubric_name\"]}')
print(f'  - Dimensions: {len(rubric[\"dimensions\"])}')
"
```

## 5. Graph Construction
```bash
python -c "
from src.core import create_auditor_graph
graph = create_auditor_graph()
print('✓ LangGraph compiled successfully')
print(f'  - Nodes: {len(graph.nodes)}')
"
```

## 6. Security Validators
```bash
python -c "
from src.utils.validators import SecurityValidator

# Test URL validation
try:
    SecurityValidator.validate_git_url('https://github.com/test/repo')
    print('✓ Git URL validation works')
except Exception as e:
    print(f'✗ Git URL validation failed: {e}')

# Test path validation  
try:
    from pathlib import Path
    SecurityValidator.validate_file_path('test.py', Path.cwd())
    print('✓ Path validation works')
except Exception as e:
    print(f'✗ Path validation failed: {e}')
"
```

## 7. CLI Interface
```bash
python -m src.main version
```

Expected output:
```
Automaton Auditor v2.0.0
Deep LangGraph Swarms for Autonomous Code Governance
```

## 8. Help Command
```bash
python -m src.main --help
```

Should show available commands: `audit`, `self-audit`, `version`

## 9. Directory Structure
```bash
ls -la audit/
```

Should show:
```
report_bypeer_received/
report_onpeer_generated/
report_onself_generated/
langsmith_logs/
```

## 10. Test Suite
```bash
pytest --collect-only
```

Should discover test files without errors.

## ✅ Full Verification Suite

Run all checks at once:

```bash
#!/bin/bash
echo "🔍 Running verification suite..."

echo -e "\n1. Module imports..."
python -c "from src.agents import *; from src.core import *; from src.tools import *; print('✓ Pass')" || echo "✗ Fail"

echo -e "\n2. Configuration..."
python -c "from src.core.config import load_rubric; load_rubric('rubric/week2_rubric.json'); print('✓ Pass')" || echo "✗ Fail"

echo -e "\n3. Graph construction..."
python -c "from src.core import create_auditor_graph; create_auditor_graph(); print('✓ Pass')" || echo "✗ Fail"

echo -e "\n4. Security validators..."
python -c "from src.utils.validators import SecurityValidator; SecurityValidator.validate_git_url('https://github.com/test/repo'); print('✓ Pass')" || echo "✗ Fail"

echo -e "\n5. CLI interface..."
python -m src.main version > /dev/null && echo "✓ Pass" || echo "✗ Fail"

echo -e "\n6. File structure..."
[ -f "src/main.py" ] && [ -f "rubric/week2_rubric.json" ] && echo "✓ Pass" || echo "✗ Fail"

echo -e "\n✅ Verification complete!"
```

## 🔧 Troubleshooting

### Import Errors
```bash
# Reinstall package in development mode
pip install -e .
```

### Missing Directories
```bash
# Recreate audit directories
mkdir -p audit/{report_bypeer_received,report_onpeer_generated,report_onself_generated,langsmith_logs}
```

### Configuration Issues
```bash
# Copy example config
cp .env.example .env
# Then edit .env with your API keys
```

## 📊 Success Criteria

All checks should show "✓ Pass". If any fail:
1. Check error messages
2. Verify Python version (3.11+)
3. Ensure virtual environment is activated
4. Reinstall dependencies: `pip install -e .`
