
import logging
import re
from typing import Any, Dict
from jinja2 import Environment, BaseLoader, TemplateError

logger = logging.getLogger(__name__)

# Use a shared environment for caching parsed templates if needed, 
# but for dynamic strings we often just use Template(str).
# However, Environment provides better control (autoescape, etc).
_env = Environment(loader=BaseLoader(), autoescape=True)

_FORMAT_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _render_format_placeholders(text: str, context: Dict[str, Any]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = context.get(key)
        return str(value) if value is not None else match.group(0)

    return _FORMAT_PATTERN.sub(_replace, text)


def render_template(template_text: str, context: Dict[str, Any]) -> str:
    """
    Render a Jinja2 template string with the given context.
    """
    if not template_text:
        return ""
    
    try:
        template = _env.from_string(template_text)
        rendered = template.render(**context)
    except TemplateError as e:
        logger.error(f"Jinja2 render error: {e}")
        rendered = template_text

    # Support legacy {placeholder} formatting after Jinja render.
    return _render_format_placeholders(rendered, context)
