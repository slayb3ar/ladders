# Ladders

Ladders is a robust yet simple web framework for python.
It combines the power of frameworks like Rails with the simplicity of frameworks like Flask.

## Quick Start

```py
from ladders import LaddersApp

# App setup
app = LaddersApp()

# Routes
@app.get("/json")
async def get_data(request):
    return app.render_response({"message": "Hello, JSON!"}, content_type='json')

@app.get("/text")
async def plain_text(request):
    return app.render_response("This is plain text", content_type='text')

@app.get("/html")
async def hello(request):
    return app.render_response(template_name="hello.html", context={"some_var": "Hello, World!"})

if __name__ == '__main__':
    app.run()

```
