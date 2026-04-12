# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import gradio as gr
import requests
import tempfile
import os
import base64
import json
import sys
import ast
import re

import uuid
from frontend.utils import email_demo, logger

BP_INFO_MARKDOWN="""
### Key Features

PDF to Markdown Service

 * Extracts content from PDFs and converts it into markdown format for further processing.

Monologue or Dialogue Creation Service

 * AI processes markdown content, enriching or structuring it to create natural and engaging audio content.

Text-to-Speech (TTS) Service

 * Converts the processed content into high-quality speech.

"""

CONFIG_INSTRUCTIONS_MARKDOWN="""
Use this editor to configure your long-reasoning agent. 

**Note:** The default configuration is for Build endpoints on the NVIDIA API Catalog. To use a local agent, ensure the compose services are running with the ``local`` profile. 

**Example**: Using a _locally_ running ``llama-3.1-8b-instruct`` NVIDIA NIM

```
{
  "reasoning": {
    "name": "meta/llama-3.1-8b-instruct",
    "api_base": "http://pdf-to-podcast-local-nim-1:8000/v1"
  },
  ...
}
```

"""

css = """
#editor-title {
    margin: auto;
    width: 100%; 
    text-align: center; 
}
"""

js_func = """
function refresh() {
    const url = new URL(window.location);
    if (url.searchParams.get('__theme') !== 'dark') {
        url.searchParams.set('__theme', 'dark');
        window.location.href = url.href;
    }
}
"""

_CONFIG_CHANGES_JS = """
async() => {
    title = document.querySelector("div#config-toolbar p");
    if (! title.innerHTML.endsWith("🟠")) { title.innerHTML = title.innerHTML.slice(0,-2) + "🟠"; };
}
"""
_SAVE_CHANGES_JS = """
async() => {
    title = document.querySelector("div#config-toolbar p");
    if (! title.innerHTML.endsWith("🟢")) { title.innerHTML = title.innerHTML.slice(0,-2) + "🟢"; };
}
"""
_SAVE_IMG = "https://media.githubusercontent.com/media/NVIDIA/nim-anywhere/main/code/frontend/_static/images/floppy.png"
_UNDO_IMG = "https://media.githubusercontent.com/media/NVIDIA/nim-anywhere/main/code/frontend/_static/images/undo.png"
_HISTORY_IMG = "https://media.githubusercontent.com/media/NVIDIA/nim-anywhere/main/code/frontend/_static/images/history.png"
_PSEUDO_FILE_NAME = "models.json 🟢"
with open("/project/models.json", "r", encoding="UTF-8") as config_file:
    _STARTING_CONFIG = config_file.read()

sys.stdout = logger.Logger("/project/frontend/output.log")

# Gradio Interface
with gr.Blocks(css=css, js=js_func) as demo:
    gr.Markdown("# NVIDIA AI Blueprint: PDF-to-Podcast")

    with gr.Row():
        with gr.Column(scale=1): 

            with gr.Tab("Full End to End Flow"):
                gr.Markdown("### Upload at least one PDF file for a file to target or as context. ")
                with gr.Row():
                    target_files = gr.File(label="Upload target PDF", file_types=[".pdf"])
                    context_files = gr.File(label="Upload context PDF", file_types=[".pdf"], file_count="multiple")
                with gr.Row():
                    settings = gr.CheckboxGroup(
                        ["Monologue Only"], label="Additional Settings", info="Customize your podcast here"
                    )   
                with gr.Accordion("Optional: Email Details", open=False):
                    gr.Markdown("Enter a recipient email here to receive your generated podcast in your inbox! \n\n**Note**: Ensure `SENDER_EMAIL` and `SENDER_EMAIL_PASSWORD` are configured in AI Workbench")
                    recipient_email = gr.Textbox(label="Recipient email", placeholder="Enter email here")
                                 
                generate_button = gr.Button("Generate Podcast")

            with gr.Tab("Agent Configurations"):
                gr.Markdown(CONFIG_INSTRUCTIONS_MARKDOWN)
                with gr.Row(elem_id="config-row"):
                    with gr.Column():
                        with gr.Group(elem_id="config-wrapper"):
                            with gr.Row(elem_id="config-toolbar", elem_classes=["toolbar"]):
                                file_title = gr.Markdown(_PSEUDO_FILE_NAME, elem_id="editor-title")
                                save_btn = gr.Button("", icon=_SAVE_IMG, elem_classes=["toolbar"])
                                undo_btn = gr.Button("", icon=_UNDO_IMG, elem_classes=["toolbar"])
                                reset_btn = gr.Button("", icon=_HISTORY_IMG, elem_classes=["toolbar"])
                            with gr.Row(elem_id="config-row-box"):
                                editor = gr.Code(
                                    elem_id="config-editor",
                                    interactive=True,
                                    language="json",
                                    show_label=False,
                                    container=False,
                                )

            with gr.Tab("Architecture Diagram"):
                gr.Markdown(BP_INFO_MARKDOWN)
                gr.Image(value="frontend/static/diagram.png")

        with gr.Column(scale=1):
            gr.Markdown("<br />")
            output = gr.Textbox(label="Outputs", placeholder="Outputs will show here when executing", max_lines=20, lines=20)
            output_file = gr.File(visible=False, interactive=False)
            transcript_file = gr.File(visible=False, interactive=False)
            history_file = gr.File(visible=False, interactive=False)

    timer = gr.Timer()
    timer.tick(logger.read_logs, None, output)
    
    def read_chain_config() -> str:
        """Read the chain config file."""
        with open("/project/models.json", "r", encoding="UTF-8") as cf:
            return cf.read()

    demo.load(read_chain_config, outputs=editor)

    undo_btn.click(read_chain_config, outputs=editor)
    undo_btn.click(None, js=_SAVE_CHANGES_JS)
    
    @reset_btn.click(outputs=editor)
    def reset_demo() -> str:
        """Reset the configuration to the starting config."""
        return _STARTING_CONFIG

    @save_btn.click(inputs=editor)
    def save_chain_config(config_txt: str) -> None:
        """Save the user's config file."""
        # validate json
        try:
            config_data = json.loads(config_txt)
        except Exception as err:
            raise SyntaxError(f"Error validating JSON syntax:\n{err}") from err

        # save configuration
        with open("/project/models.json", "w", encoding="UTF-8") as cf:
            cf.write(config_txt)

    save_btn.click(None, js=_SAVE_CHANGES_JS)

    # %% editor actions
    editor.input(None, js=_CONFIG_CHANGES_JS)

    def validate_sender(sender):
        if sender is None:
            return False
        regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(regex, sender))

    def get_transcript(filename, job_id):
        service = os.environ["API_SERVICE_URL"]
        url = f"{service}/saved_podcast/{job_id}/transcript"
        params = {"userId": "test-userid"}
        filepath = "/project/frontend/demo_outputs/transcript_" + filename + ".json"
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            json_data = response.json()
            with open(filepath, "w") as file:
                json.dump(json_data, file)
            print(f"JSON data saved to {filepath}")
            return filepath
        else:
            print(f"Error retrieving transcript: {response.status_code}")
            return filepath

    def get_history(filename, job_id):
        service = os.environ["API_SERVICE_URL"]
        url = f"{service}/saved_podcast/{job_id}/history"
        params = {"userId": "test-userid"}
        filepath = "/project/frontend/demo_outputs/generation_history_" + filename + ".json"
        response = requests.get(url, params=params)

        if response.status_code == 200:
            json_data = response.json()
            with open(filepath, "w") as file:
                json.dump(json_data, file)
            print(f"JSON data saved to {filepath}")
            return filepath
        else:
            print(f"Error retrieving generation_history: {response.status_code}")
            return filepath

    def generate_podcast(target, context, recipient, settings):
        if target is None or len(target) == 0:
            gr.Warning("Target PDF upload not detected. Please upload a target PDF file and try again. ")
            return gr.update(visible=False)

        # Prevent TypeError when accordion not opened (recipient is None)
        recipient = recipient or ""

        sender_email = os.environ["SENDER_EMAIL"] if "SENDER_EMAIL" in os.environ else None
        
        if isinstance(target, str):
            target = [target]
        if isinstance(context, str):
            context = [context]
        
        base_url = os.environ["API_SERVICE_URL"]
        monologue = True if "Monologue Only" in settings else False
        vdb = False # True if "Vector Database" in settings else False
        filename = str(uuid.uuid4())
        sender_validation = validate_sender(sender_email)
        if not sender_validation and len(recipient) > 0:
            gr.Warning("SENDER_EMAIL not detected or malformed. Please fix or remove recipient email and try again. You may need to restart the container for Environment Variable changes to take effect. ")
            return gr.update(visible=False)
        elif sender_validation and len(recipient) > 0 and "SENDER_EMAIL_PASSWORD" not in os.environ: 
            gr.Warning("SENDER_EMAIL_PASSWORD not detected. Please fix or remove recipient email and try again. You may need to restart the container for Environment Variable changes to take effect. ")
            return gr.update(visible=False)
        email = [recipient] if (sender_validation and len(recipient) > 0 and "SENDER_EMAIL_PASSWORD" in os.environ) else [filename + "@"] # delimiter

        # Generate podcast
        job_id = email_demo.test_api(base_url, target, context, email, monologue, vdb)

        # Send file via email
        if sender_validation and len(recipient) > 0 and "SENDER_EMAIL_PASSWORD" in os.environ:
            email_demo.send_file_via_email("/project/frontend/demo_outputs/" + recipient.split('@')[0] + "-output.mp3", sender_email, recipient)
            return gr.update(value="/project/frontend/demo_outputs/" + recipient.split('@')[0] + "-output.mp3", label="podcast audio", visible=True), gr.update(value=get_transcript(recipient.split('@')[0], job_id), label="podcast transcript", visible=True), gr.update(value=get_history(recipient.split('@')[0], job_id), label="generation history", visible=True)

        return gr.update(value="/project/frontend/demo_outputs/" + filename + "-output.mp3", label="podcast audio", visible=True), gr.update(value=get_transcript(filename, job_id), label="podcast transcript", visible=True), gr.update(value=get_history(filename, job_id), label="generation history", visible=True)

    generate_button.click(generate_podcast, [target_files, 
                                             context_files, 
                                             recipient_email, 
                                             settings], [output_file, transcript_file, history_file])

# Launch Gradio app
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", root_path=os.environ.get("PROXY_PREFIX"))
