import os
import sys
from dotenv import load_dotenv

# Load environment variables before imports
load_dotenv()

try:
    from src.agents.judges.prosecutor import Prosecutor
    from src.core.state import Evidence
    from src.core.config import get_config

    cfg = get_config(require_llm_keys=False)
    
    print("--- System Boot ---")
    print(f"Using model: {cfg.default_llm_model}")

    prosecutor = Prosecutor()
    
    # Mocking the Evidence
    fake_evidence = {
        'RepoInvestigator': [
            Evidence(
                found=True, 
                content='Found raw os.system call in git_tools.py', 
                location='src/tools/git_tools.py', 
                confidence=1.0, 
                detective_name='RepoInvestigator'
            )
        ]
    }
    
    criterion = {
        'id': 'forensic_accuracy_code',
        'name': 'Forensic Accuracy (Codebase)',
        'target_artifact': 'github_repo',
        'forensic_instruction': 'Check for sandboxed git operations',
        'judicial_logic': {
            'prosecutor': 'Charge with Security Negligence if os.system is used'
        }
    }

    print("--- Executing Prosecutor Analysis ---")
    opinion = prosecutor.render_opinion(criterion, fake_evidence)
    print(f"Opinion Received: {opinion}")

except ImportError as e:
    print(f"IMPORT ERROR: Check your PYTHONPATH. {e}")
except Exception as e:
    print(f"RUNTIME ERROR: {e}")