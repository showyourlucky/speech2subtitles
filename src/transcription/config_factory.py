"""
转录配置构建工具

统一处理以下逻辑，避免多处重复实现：
1. 解析模型类型（含异常回退）
2. 解析语言提示（以 pipeline 逻辑为主）
3. 构建 TranscriptionConfig（含 QWEN_ARS 专属参数）
"""

from typing import Any, Callable, Optional

from src.transcription.models import (
    LanguageCode,
    ProcessorType,
    TranscriptionConfig,
    TranscriptionModel,
)


def resolve_transcription_model_type(
    config: Any,
    on_warning: Optional[Callable[[str], None]] = None,
) -> TranscriptionModel:
    """
    解析当前配置应使用的转录模型类型。

    优先读取活跃模型方案中的 model_type，若不存在或非法则回退为 sense_voice。
    """
    try:
        active_model_profile = config.get_active_model_profile()
        raw_model_type = getattr(
            active_model_profile,
            "model_type",
            TranscriptionModel.SENSE_VOICE.value,
        )
    except Exception as e:
        if on_warning:
            on_warning(f"读取活跃模型方案失败，回退到sense_voice: {e}")
        return TranscriptionModel.SENSE_VOICE

    if not raw_model_type:
        return TranscriptionModel.SENSE_VOICE

    # 优先按枚举值匹配，兼容旧配置场景
    try:
        return TranscriptionModel(raw_model_type)
    except ValueError:
        # 再按枚举名称匹配（如 QWEN_ARS）
        model_name = str(raw_model_type).strip().upper()
        if model_name in TranscriptionModel.__members__:
            return TranscriptionModel[model_name]

    if on_warning:
        on_warning(f"未识别的model_type配置: {raw_model_type}，已回退到sense_voice")
    return TranscriptionModel.SENSE_VOICE


def _parse_language_hint(
    raw_language: Optional[str],
    default: LanguageCode = LanguageCode.AUTO,
) -> LanguageCode:
    """将字符串语言配置解析为 LanguageCode（不包含场景默认策略）。"""
    if raw_language is None:
        return default

    normalized = str(raw_language).strip().lower()
    if normalized in {"zh", "zh-cn", "chinese", "cn"}:
        return LanguageCode.CHINESE
    if normalized in {"en", "en-us", "english"}:
        return LanguageCode.ENGLISH
    if normalized in {"auto", "自动"}:
        return LanguageCode.AUTO
    return default


def resolve_transcription_language(
    config: Any,
    on_warning: Optional[Callable[[str], None]] = None,
    on_info: Optional[Callable[[str], None]] = None,
) -> LanguageCode:
    """
    解析当前配置应使用的识别语言（以 pipeline 逻辑为主）。

    规则：
    1. 若配置中显式提供 transcription_language，则优先使用。
    2. 若未配置且为系统音频，默认使用中文提示。
    3. 其它场景回退为自动识别。
    """
    raw_language = getattr(config, "transcription_language", None)
    if raw_language is not None:
        parsed = _parse_language_hint(raw_language, default=LanguageCode.AUTO)
        if parsed != LanguageCode.AUTO or str(raw_language).strip().lower() in {"auto", "自动"}:
            return parsed
        if on_warning:
            on_warning(f"未识别的 transcription_language 配置: {raw_language}，已回退到默认策略")

    if getattr(config, "input_source", None) == "system":
        if on_info:
            on_info("系统音频默认启用中文识别提示(language=zh)，可降低中日混淆导致的漏字")
        return LanguageCode.CHINESE

    return LanguageCode.AUTO


def build_transcription_config(
    config: Any,
    *,
    gpu_available: Optional[bool] = None,
    on_warning: Optional[Callable[[str], None]] = None,
    on_info: Optional[Callable[[str], None]] = None,
) -> TranscriptionConfig:
    """
    构建统一的转录配置对象。

    Args:
        config: 全局配置对象（需提供 model_path/use_gpu/sample_rate/get_active_model_profile）
        gpu_available: GPU可用性，None 表示仅依据 use_gpu 决定
        on_warning: 警告输出回调
        on_info: 信息输出回调
    """
    resolved_model = resolve_transcription_model_type(
        config,
        on_warning=on_warning,
    )
    resolved_language = resolve_transcription_language(
        config,
        on_warning=on_warning,
        on_info=on_info,
    )
    use_gpu = bool(config.use_gpu and (gpu_available if gpu_available is not None else True))

    active_model_profile = config.get_active_model_profile()
    qwen_ars_kwargs = {}
    if resolved_model == TranscriptionModel.QWEN_ARS:
        try:
            
            qwen_ars_kwargs = {
                "hotwords": getattr(active_model_profile, "hotwords", ""),
                "feature_dim": getattr(active_model_profile, "feature_dim", 128),
                "max_total_len": getattr(active_model_profile, "max_total_len", 512),
                "max_new_tokens": getattr(active_model_profile, "max_new_tokens", 128),
                "temperature": getattr(active_model_profile, "temperature", 1.0),
                "top_p": getattr(active_model_profile, "top_p", 0.8),
                "seed": getattr(active_model_profile, "seed", 48),
            }
        except Exception as e:
            if on_warning:
                on_warning(f"读取QWEN_ARS参数失败，将使用默认值: {e}")

    return TranscriptionConfig(
        model=resolved_model,
        model_path=config.model_path,
        language=resolved_language,
        processor_type=ProcessorType.GPU if use_gpu else ProcessorType.CPU,
        sample_rate=config.sample_rate,
        use_gpu=use_gpu,
        num_threads = active_model_profile.num_threads if hasattr(active_model_profile, "num_threads") else 4,
        **qwen_ars_kwargs,
    )
