"""GUI组件"""

from .control_panel import TranscriptionControlPanel
from .audio_source_selector import AudioSourceSelector
from .status_monitor import StatusMonitorPanel
from .result_display import TranscriptionResultDisplay

__all__ = [
    'TranscriptionControlPanel',
    'AudioSourceSelector',
    'StatusMonitorPanel',
    'TranscriptionResultDisplay',
]
