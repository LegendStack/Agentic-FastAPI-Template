# Demo Agent Package
# This package contains a comprehensive demo agent showcasing all LegendStack features.

from .config import DemoAgentConfig
from .demo_agent import LegendDemoAgent

__all__ = ["LegendDemoAgent", "DemoAgentConfig"]
