"""
页面解析工具
"""
from typing import Any, Optional

from playwright.async_api import Page

from app.core.logger import logger


class PageParser:
    """页面解析器"""

    def __init__(self, page: Page):
        self.page = page

    async def get_page_structure(self) -> dict[str, Any]:
        """获取页面结构"""
        try:
            # 获取所有可交互元素
            elements = await self.page.evaluate("""
                () => {
                    const results = [];

                    // 获取所有可点击元素
                    const clickables = document.querySelectorAll('button, a, [role="button"], input[type="button"], input[type="submit"]');
                    clickables.forEach((el, i) => {
                        results.push({
                            type: 'clickable',
                            tag: el.tagName.toLowerCase(),
                            text: el.innerText || el.value || '',
                            id: el.id,
                            className: el.className,
                            selector: el.id ? `#${el.id}` : null
                        });
                    });

                    // 获取所有输入框
                    const inputs = document.querySelectorAll('input, textarea, select');
                    inputs.forEach((el, i) => {
                        results.push({
                            type: 'input',
                            tag: el.tagName.toLowerCase(),
                            inputType: el.type,
                            name: el.name,
                            placeholder: el.placeholder,
                            id: el.id,
                            className: el.className
                        });
                    });

                    return results;
                }
            """)

            return {"success": True, "elements": elements}

        except Exception as e:
            logger.error(f"Failed to get page structure: {e}")
            return {"success": False, "error": str(e)}

    async def get_readable_content(self) -> str:
        """获取可读内容"""
        try:
            content = await self.page.evaluate("""
                () => {
                    // 简单提取主要内容
                    const main = document.querySelector('main, article, .content, #content');
                    if (main) return main.innerText;

                    // 回退到 body
                    return document.body.innerText;
                }
            """)

            return content or ""

        except Exception as e:
            logger.error(f"Failed to get readable content: {e}")
            return ""

    async def find_element_by_text(self, text: str) -> Optional[str]:
        """通过文本查找元素"""
        try:
            selector = await self.page.evaluate(f"""
                () => {{
                    const elements = document.querySelectorAll('button, a, span, div, p, label');
                    for (const el of elements) {{
                        if (el.innerText && el.innerText.includes('{text}')) {{
                            if (el.id) return '#' + el.id;
                            return el.tagName.toLowerCase() + ':contains("' + text + '")';
                        }}
                    }}
                    return null;
                }}
            """)

            return selector

        except Exception as e:
            logger.error(f"Failed to find element by text: {e}")
            return None

    async def get_form_fields(self) -> list[dict[str, Any]]:
        """获取表单字段"""
        try:
            fields = await self.page.evaluate("""
                () => {
                    const forms = document.querySelectorAll('form');
                    const results = [];

                    forms.forEach(form => {
                        const inputs = form.querySelectorAll('input, textarea, select');
                        inputs.forEach(input => {
                            results.push({
                                tag: input.tagName.toLowerCase(),
                                type: input.type,
                                name: input.name,
                                id: input.id,
                                placeholder: input.placeholder,
                                required: input.required,
                                label: input.labels ? input.labels[0]?.innerText : null
                            });
                        });
                    });

                    return results;
                }
            """)

            return fields or []

        except Exception as e:
            logger.error(f"Failed to get form fields: {e}")
            return []
