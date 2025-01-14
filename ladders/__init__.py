# LIBRARY CODE

##################################################################################
# CONFIG SETTINGS
import os
from pydantic_settings import BaseSettings
class LaddersSettings(BaseSettings):
    DEBUG: bool = os.getenv('DEBUG', 'True').lower() == 'true'
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'this-is-a-secret-key')
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite:///./db.sqlite3')
    TEMPLATES_DIR: str = os.getenv('TEMPLATES_DIR', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ladders', 'templates'))
    STATIC_URL: str = '/static/'
    STATIC_ROOT: str = os.getenv('STATIC_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'staticfiles'))
    STATICFILES_DIRS: list = [
        os.getenv('STATICFILES_DIR', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ladders', 'static')),
    ]
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

##################################################################################
# END CONFIG SETTINGS



##################################################################################
# TEMPLATING PARSER
import re
import sys
from io import StringIO
from pathlib import Path

class TemplateParser:
    def __init__(self, template_dir=None):
        self.template_dir = template_dir
        self._exec_pattern = re.compile(r'<%([\s\S]+?)%>')  # Inline Python execution
        self._eval_pattern = re.compile(r'%%([^}]+?)%%')   # Inline Python evaluation
        self._block_pattern = re.compile(r'{%\s*block\s+(\w+)\s*%}([\s\S]*?){%\s*endblock\s*%}')  # Block pattern
        self._include_pattern = re.compile(r'{%\s*include\s+["\']([\w\/\-\.]+)["\']\s*%}')  # Include pattern
        self._extends_pattern = re.compile(r'{%\s*extends\s+["\']([\w\/\-\.]+)["\']\s*%}')  # Extends pattern

    def render(self, template_name, context=None):
        if context is None:
            context = {}

        # Step 1: Process the template
        file_path = Path(f'{self.template_dir}/{template_name}')
        if not file_path.exists():
            raise FileNotFoundError(f"Template '{template_name}' not found.")

        rendered_template = file_path.read_text(encoding='utf-8')

        # Step 2: Process template inheritance (if a base template exists)
        rendered_template = self.process_inheritance(rendered_template, context)

        # Step 3: Process includes (e.g., footer, header)
        rendered_template = self.process_includes(rendered_template, context)

        # Step 4: Process inline Python code in the template content
        rendered_template = self.execute_python(rendered_template, context)

        return rendered_template

    def execute_python(self, content, context):
        """
        Preprocess custom Python code blocks in the rendered template.
        """
        buffer = context['buffer'] = StringIO()
        _exec_pattern, _eval_pattern = self._exec_pattern, self._eval_pattern

        def _process(match, is_exec):
            # Extract and format code
            code = match.group(1)
            if not code.strip():
                return ''

            # Correct indentation
            lines = code.splitlines()
            if not lines:
                return ''

            # Find minimum indentation for non-empty lines
            min_indent = min(len(line) - len(line.lstrip()) for line in lines if line.strip())
            code = '\n'.join(line[min_indent:] for line in lines)

            # Execute or evaluate
            if is_exec:
                _stdout, sys.stdout = sys.stdout, buffer
                exec(code, context)
                sys.stdout = _stdout
                result = buffer.getvalue().replace('\n', '')
                buffer.seek(0)
                buffer.truncate()
                return result
            else:
                return str(eval(code.strip(), context))

        # Process execution and evaluation blocks
        content = _exec_pattern.sub(lambda m: _process(m, True), content)
        content = _eval_pattern.sub(lambda m: _process(m, False), content)
        return content

    def process_inheritance(self, content, context):
        """
        Process template inheritance (e.g., `{% extends 'base.html' %}`).
        """
        match = self._extends_pattern.search(content)
        if match:
            base_template_name = match.group(1)
            # Load the base template
            base_template = self.render(base_template_name, context)
            # Remove the extends statement from content
            content = re.sub(self._extends_pattern, '', content)

            # Extract blocks from the child template
            child_blocks = dict(self.extract_blocks(content))

            # Replace blocks in the base template with content from the child template
            for block_name, block_content in child_blocks.items():
                base_template = base_template.replace('{% block ' + block_name + ' %}', block_content)

            # Ensure blocks that are not defined in the child template are handled
            base_template = self.replace_default_blocks(base_template, child_blocks)

            return base_template
        return content

    def extract_blocks(self, content):
        """
        Extract blocks from the template content (e.g., block content between `{% block %}` tags).
        """
        blocks = {}
        for match in self._block_pattern.finditer(content):
            block_name = match.group(1)
            block_content = match.group(2)
            blocks[block_name] = block_content
        return blocks.items()

    def replace_default_blocks(self, base_template, child_blocks):
       """
       Ensures that any block not defined in the child template is replaced with empty content
       or default content.
       """
       for match in self._block_pattern.finditer(base_template):
           block_name = match.group(1)
           if block_name not in child_blocks:
               base_template = base_template.replace('{% block ' + block_name + ' %}', '')
       return base_template

    import re
    from pathlib import Path

    def process_includes(self, content, context):
        """
        Process includes (e.g., `{% include 'footer.html' %}`).
        """
        include_pattern = re.compile(r'{%\s*include\s+\'([^\']+)\'\s*%}')
        matches = include_pattern.findall(content)
        included_templates = set()

        for match in matches:
            include_template = match

            # Skip if this template is already included
            if include_template in included_templates:
                continue

            # Mark this template as included
            included_templates.add(include_template)

            # Construct the full path to the included template
            include_file_path = Path(f'{self.template_dir}/{include_template}')

            if include_file_path.exists():
                # Read the content of the included template
                with open(include_file_path, 'r') as f:
                    include_content = f.read()
                # Replace the include tag with the content of the included template
                content = content.replace(f'{{% include \'{include_template}\' %}}', include_content)
            else:
                raise FileNotFoundError(f"Included template '{include_template}' not found.")
        return content





##################################################################################
# END TEMPLATING PARSER

##################################################################################
# MAIN APP
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, FileResponse
from starlette.routing import Route
import uvicorn
import mimetypes
import os

class LaddersApp:
    def __init__(self, settings=LaddersSettings()):
        self.app = Starlette(debug=settings.DEBUG, routes=[])
        self.settings = settings
        self._routes = {}

    def _route_decorator(self, method):
        def decorator(path, name=None):
            def wrapper(func):
                async def wrapper_with_params(request):
                    try:
                        return await func(request, **request.path_params)
                    except TypeError as e:
                        raise HTTPException(status_code=400, detail=str(e))

                route = Route(path, wrapper_with_params, methods=[method.upper()], name=name)
                self.app.routes.append(route)
                if name:
                    self._routes[name] = route
                return func
            return wrapper
        return decorator

    def get(self, path, name=None):
        return self._route_decorator('get')(path, name)

    def post(self, path, name=None):
        return self._route_decorator('post')(path, name)

    def put(self, path, name=None):
        return self._route_decorator('put')(path, name)

    def delete(self, path, name=None):
        return self._route_decorator('delete')(path, name)

    def patch(self, path, name=None):
        return self._route_decorator('patch')(path, name)

    def url_for(self, name, **path_params):
        try:
            route = self._routes[name]
            return route.url_path_for(name, **path_params)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Route with name '{name}' not found")

    def include(self, routes, prefix='', namespace=''):
        for route in routes:
            new_path = f"{prefix}{route.path}"
            new_name = f"{namespace}:{route.name}" if namespace and route.name else route.name
            new_route = Route(
                new_path,
                route.endpoint,
                methods=route.methods,
                name=new_name
            )
            self.app.routes.append(new_route)
            if new_name:
                self._routes[new_name] = new_route

    def render(self, template_name, context=None, template_dir=None):
        if context is None:
            context = {}
        if template_dir is None:
            template_dir = self.settings.TEMPLATES_DIR
        template_parser = TemplateParser(template_dir=template_dir)
        return template_parser.render(template_name, context)

    def render_response(self, content=None, content_type=None, status=200, template_name=None, context={}):
        if template_name:
            rendered = self.render(template_name, context)
            return HTMLResponse(content=rendered, status_code=status)
        elif content_type == 'json':
            return JSONResponse(content=content, status_code=status)
        elif content_type == 'text':
            return PlainTextResponse(content=str(content), status_code=status)
        else:
            return PlainTextResponse(content=str(content), status_code=status)

    def send_from_directory(self, directory, filename, as_attachment=False):
        """
        Serves a file from the given directory.

        Parameters:
            directory (str): The directory where the file resides.
            filename (str): The name of the file to serve.
            as_attachment (bool): If True, the file will be served as an attachment.

        Returns:
            FileResponse: Response object serving the file.
        """
        # Build the full path to the file
        file_path = os.path.join(directory, filename)

        # Check if the file exists
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail=f"File '{filename}' not found in directory '{directory}'")

        # Detect the content type
        mime_type, _ = mimetypes.guess_type(file_path)
        headers = {}
        if as_attachment:
            headers['Content-Disposition'] = f'attachment; filename="{filename}"'

        # Serve the file
        return FileResponse(file_path, media_type=mime_type, headers=headers)

    def abort(self, status_code, detail=None):
        """
        Aborts the current request with a specific HTTP status code.

        Parameters:
            status_code (int): The HTTP status code to return.
            detail (str): A message providing more details about the error.

        Raises:
            HTTPException: Custom HTTP exception for the given status code.
        """
        raise HTTPException(status_code=status_code, detail=detail)

    def run(self, host='127.0.0.1', port=8080):
        uvicorn.run(self.app, host=host, port=port, loop="uvloop")

    # Add this method to make the app ASGI-compliant
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)
##################################################################################
# END MAIN APP
#
#
