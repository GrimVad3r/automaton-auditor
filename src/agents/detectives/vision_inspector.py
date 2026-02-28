"""
VisionInspector: The Diagram Detective (Optional)
Extracts images from the PDF and summarizes them with a multimodal LLM when available.
Falls back to structural evidence if no images or model credentials are present.
"""

import base64
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pypdf import PdfReader
from langchain_openai import ChatOpenAI

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:  # optional
    ChatAnthropic = None

try:
    from langchain_groq import ChatGroq
except ImportError:  # optional
    ChatGroq = None

from ...core.config import get_config
from ...core.state import AgentState, Evidence
from ...utils.exceptions import NodeExecutionError
from ...utils.logger import get_logger

logger = get_logger()


class VisionInspector:
    """
    Detective agent that analyzes visual diagrams.
    """

    def __init__(self):
        self.config = get_config(require_llm_keys=False)

    def investigate(self, state: AgentState) -> Dict:
        """
        Execute visual analysis of diagrams.
        """
        logger.log_node_start("VisionInspector")
        start_time = time.time()

        try:
            pdf_path = Path(state["pdf_path"])
            images = self._extract_images(pdf_path)

            evidence_list: List[Evidence] = []

            if not images:
                evidence_list.append(
                    Evidence(
                        found=False,
                        content="No extractable images found in PDF; visual inspection skipped.",
                        location=str(pdf_path),
                        confidence=0.3,
                        detective_name="VisionInspector",
                    )
                )
            else:
                summary = self._summarize_images(images)
                evidence_list.append(
                    Evidence(
                        found=True,
                        content=summary,
                        location=str(pdf_path),
                        confidence=0.65 if "LLM unavailable" in summary else 0.85,
                        detective_name="VisionInspector",
                    )
                )

            duration = time.time() - start_time
            logger.log_node_complete("VisionInspector", duration)

            return {
                "evidences": {
                    "VisionInspector": evidence_list,
                }
            }

        except Exception as e:
            duration = time.time() - start_time
            logger.log_node_error("VisionInspector", e)
            raise NodeExecutionError("VisionInspector", e)

    def _extract_images(self, pdf_path: Path) -> List[bytes]:
        """Extract raw image bytes from the PDF."""
        images: List[bytes] = []
        try:
            reader = PdfReader(str(pdf_path))
            for page in reader.pages:
                if "/Resources" not in page:
                    continue
                resources = page["/Resources"]
                xobject = resources.get("/XObject")
                if not xobject:
                    continue
                for obj in xobject:
                    stream = xobject[obj]
                    if stream.get("/Subtype") == "/Image":
                        data = stream.get_data()
                        if data:
                            images.append(data)
        except Exception as exc:
            logger.warning(f"Image extraction failed: {exc}")
        return images

    def _summarize_images(self, images: List[bytes]) -> str:
        """Summarize images with a multimodal model when keys are available."""
        llm, provider = self._build_vision_llm()
        if llm is None:
            return f"Extracted {len(images)} image(s). LLM unavailable; stored counts only."

        try:
            b64 = base64.b64encode(images[0]).decode("utf-8")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Summarize the architectural diagram. Focus on components and data flows. Respond in <=120 characters.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ]
            resp = llm.invoke(messages)
            summary_text = getattr(resp, "content", "") or str(resp)
            return f"Detected {len(images)} image(s) via {provider}. Summary: {summary_text}"
        except Exception as exc:
            logger.warning(f"Vision summarization failed: {exc}")
            return f"Extracted {len(images)} image(s). LLM unavailable; stored counts only."

    def _build_vision_llm(self) -> Tuple[Optional[object], Optional[str]]:
        """
        Select a vision-capable LLM based on available API keys (in priority order).
        """
        if self.config.openai_api_key:
            return (
                ChatOpenAI(
                    model=self.config.default_vision_model,
                    temperature=0.1,
                    max_tokens=256,
                ),
                "openai",
            )

        if self.config.anthropic_api_key and ChatAnthropic:
            return (
                ChatAnthropic(
                    model="claude-3-5-sonnet-latest",
                    temperature=0.1,
                    max_tokens=256,
                ),
                "anthropic",
            )

        if self.config.groq_api_key and ChatGroq:
            model_name = self.config.default_vision_model
            return (
                ChatGroq(
                    model=model_name,
                    temperature=0.1,
                    max_tokens=256,
                    api_key=self.config.groq_api_key,
                ),
                "groq",
            )

        # HuggingFace multimodal could be added here once supported.
        return None, None


# Node function for LangGraph
def vision_inspector_node(state: AgentState) -> Dict:
    """
    LangGraph node wrapper for VisionInspector.
    """
    inspector = VisionInspector()
    return inspector.investigate(state)
