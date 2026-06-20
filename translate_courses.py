import os
import json
import re
import time
import sys
import traceback
from deep_translator import GoogleTranslator

# Initialize the translator
translator = GoogleTranslator(source='en', target='ru')

def translate_chunk_with_retry(chunk, translator):
    if not chunk.strip():
        return chunk
    for attempt in range(5):
        try:
            time.sleep(0.3)  # Be polite to the translation service
            res = translator.translate(chunk)
            if res is None:
                print(f"  [Warning] Translation returned None for chunk of length {len(chunk)}. Retrying ({attempt+1}/5)...")
                time.sleep(2 * (attempt + 1))
                continue
            return res
        except Exception as e:
            print(f"  [Warning] Translation failed: {e}. Retrying ({attempt+1}/5)...")
            time.sleep(2 * (attempt + 1))
    print("  [Error] Translation failed after 5 attempts. Keeping original text.")
    return chunk

def translate_text_segment(text, translator):
    if not text.strip():
        return text
    
    # 1. Extract and replace markdown links [text](url)
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    urls = []
    def link_replacer(match):
        text_part = match.group(1)
        url_part = match.group(2)
        urls.append(url_part)
        return f"[{text_part}](XYZURL{len(urls)-1}XYZ)"
        
    protected_text = link_pattern.sub(link_replacer, text)
    
    # 2. Extract and replace inline code `code`
    inline_pattern = re.compile(r'`([^`]+)`')
    inline_codes = []
    def inline_replacer(match):
        code_part = match.group(1)
        inline_codes.append(code_part)
        return f"`XYZCODE{len(inline_codes)-1}XYZ`"
        
    protected_text = inline_pattern.sub(inline_replacer, protected_text)

    # 3. Translate in chunks of under 3500 chars to respect translation size limits
    lines = protected_text.split('\n')
    translated_lines = []
    current_chunk = []
    current_len = 0
    
    for line in lines:
        if current_len + len(line) + 1 > 3500:
            chunk_to_translate = '\n'.join(current_chunk)
            translated_chunk = translate_chunk_with_retry(chunk_to_translate, translator)
            translated_lines.append(translated_chunk)
            current_chunk = [line]
            current_len = len(line)
        else:
            current_chunk.append(line)
            current_len += len(line) + 1
            
    if current_chunk:
        chunk_to_translate = '\n'.join(current_chunk)
        translated_chunk = translate_chunk_with_retry(chunk_to_translate, translator)
        translated_lines.append(translated_chunk)
        
    translated_text = '\n'.join(translated_lines)
    
    # 4. Restore inline code
    for idx, code in enumerate(inline_codes):
        placeholder = f"XYZCODE{idx}XYZ"
        translated_text = re.sub(rf'XYZCODE{idx}XYZ', code, translated_text, flags=re.IGNORECASE)
        
    # 5. Restore URLs
    for idx, url in enumerate(urls):
        placeholder = f"XYZURL{idx}XYZ"
        translated_text = re.sub(rf'XYZURL{idx}XYZ', url, translated_text, flags=re.IGNORECASE)
        
    return translated_text

def translate_markdown(content, translator):
    # Split content by code blocks (```)
    parts = content.split("```")
    translated_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Code block - preserve it completely
            translated_parts.append(part)
        else:
            # Plain text - translate it
            translated_parts.append(translate_text_segment(part, translator))
            
    return "```".join(translated_parts)

def translate_ipynb(file_path, translator):
    print(f"Translating notebook: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for cell in data.get('cells', []):
            if cell.get('cell_type') == 'markdown':
                source = cell.get('source', [])
                if isinstance(source, list):
                    original_text = "".join(source)
                else:
                    original_text = source
                    
                translated_text = translate_markdown(original_text, translator)
                
                # Split by \n and keep the newlines for standard Jupyter formatting
                lines = translated_text.split('\n')
                source_lines = []
                for i, line in enumerate(lines):
                    if i < len(lines) - 1:
                        source_lines.append(line + '\n')
                    else:
                        source_lines.append(line)
                cell['source'] = source_lines
                
        new_file_path = file_path.replace('.ipynb', '_RU.ipynb')
        with open(new_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print(f"Successfully saved translated notebook to: {new_file_path}")
    except Exception as e:
        print(f"Error translating notebook {file_path}: {e}")
        traceback.print_exc()

def translate_md_file(file_path, translator):
    print(f"Translating markdown file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        translated_content = translate_markdown(content, translator)
        
        new_file_path = file_path.replace('.md', '_RU.md')
        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        print(f"Successfully saved translated markdown to: {new_file_path}")
    except Exception as e:
        print(f"Error translating markdown file {file_path}: {e}")

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
        if os.path.isabs(target_dir):
            root_dir = target_dir
        else:
            root_dir = os.path.join(root_dir, target_dir)
            
    print(f"Scanning directory: {root_dir}")
    
    for dirpath, _, filenames in os.walk(root_dir):
        # Skip git folder
        if '.git' in dirpath.split(os.sep):
            continue
            
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            
            # Skip already translated files and this script
            if filename.endswith('_RU.ipynb') or filename.endswith('_RU.md') or filename == 'translate_courses.py':
                continue
                
            if filename.endswith('.ipynb'):
                translate_ipynb(file_path, translator)
            elif filename.endswith('.md'):
                translate_md_file(file_path, translator)

if __name__ == '__main__':
    main()
