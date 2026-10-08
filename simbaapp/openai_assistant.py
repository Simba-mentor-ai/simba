import os
import base64
from datetime import datetime
from openai import OpenAI
from typing import List, Dict, Any, Optional
import logging
from .templates import build_system_prompt

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# def _build_instructions(activity_data: Dict[str, Any], has_files: bool = False) -> str:
#     """Build the instructions for the OpenAI assistant based on activity data"""
    
#     course_title = activity_data.get('course_title', 'this course')
    
#     # Get activity-specific information
#     activity_title = activity_data.get('title', '')
#     activity_description = activity_data.get('description', '')
    
#     adj1 = activity_data.get('agent_attitude', 'friendly')
#     expert_mode = activity_data.get('expert_mode', False)
#     allow_emojis = activity_data.get('allow_emojis', True)
#     questions = activity_data.get('questions', [])
#     subjects = activity_data.get('subjects', '')
#     restrict_to_subject = activity_data.get('restrict_to_subject', False)
#     trust_document = activity_data.get('trust_document', True)
#     word_limit = activity_data.get('word_limit', 0)
#     custom_prompt = activity_data.get('custom_prompt', '')
#     allow_bot_questions = activity_data.get('allow_questions', True)

#     def emoji_gen(use_emojis):
#         return ", using emojis where possible." if use_emojis else "."

#     def questions_gen_str(questions_list):
#         if not questions_list:
#             return ""
#         result = ""
#         for i, question in enumerate(questions_list, 1):
#             result += f"Question {i}: {question}\n"
#         return result.strip()

#     def subjects_gen_str(subjects_text, restricted):
#         if not subjects_text:
#             return ""
#         result = "You should help the student to reflect in depth on the following course subjects:\n"
#         result += f"<Beginning of the course subjects>\n{subjects_text}\n<end of the course subjects>\n"
#         if restricted:
#             result += "You should only speak of those listed subjects. Avoid as much as possible speaking of other subjects, and steer back the student to the course subjects if he tries to deviate from them."
#         return result

#     def answers_gen_str(is_expert_mode):
#         if is_expert_mode:
#             return "You should not give the answer, but guide the student to answer."
#         else:
#             return "You can provide an answer to the provided questions if the student asks for it."

#     def teach_type_gen_str(is_expert_mode):
#         if is_expert_mode:
#             return "Act as a Socratic tutor, taking the initiative in getting the students to answer the questions."
#         else:
#             return "Act as a standard teacher."

#     def teaching_adj_gen_str(is_expert_mode):
#         return "socratic" if is_expert_mode else "standard"

#     def docs_gen_str(mention_documents, has_files):
#         if mention_documents and has_files:
#             return "You have access to uploaded documents for this activity. Use these documents to help answer questions and encourage students to reference them when appropriate."
#         elif mention_documents and not has_files:
#             return "Encourage them to go and read a section of the provided documents to answer."
#         elif has_files:
#             return "You have access to uploaded documents for this activity that you can reference to help students."
#         return ""

#     def files_gen_str(has_files):
#         if has_files:
#             return "\n\nIMPORTANT: This activity has uploaded files/documents available. You can search through and reference these documents to provide more accurate and detailed responses. When relevant, cite information from these documents and encourage students to explore them."
#         return ""

#     def limits_gen_str(limit):
#         return f"Your answers should be {limit} words maximum." if limit and limit != 0 else ""

#     def activity_context_gen_str(title, description):
#         """Generate activity-specific context for the prompt"""
#         context_str = ""
#         if title and description:
#             context_str = f"This specific activity is titled '{title}' and focuses on: {description}.\n\n"
#         elif title:
#             context_str = f"This specific activity is titled '{title}'.\n\n"
#         elif description:
#             context_str = f"This activity focuses on: {description}.\n\n"
#         return context_str

#     emojis_str = emoji_gen(allow_emojis)
#     questions_str = questions_gen_str(questions)
#     subjects_str = subjects_gen_str(subjects, restrict_to_subject)
#     teaching_adj_str = teaching_adj_gen_str(expert_mode)
#     answers_text = answers_gen_str(expert_mode)
#     teaching_type_text = teach_type_gen_str(expert_mode)
#     documents_str = docs_gen_str(trust_document, has_files)
#     files_str = files_gen_str(has_files)
#     limits_str = limits_gen_str(word_limit)
#     activity_context_str = activity_context_gen_str(activity_title, activity_description)

#     full_template = f"""You are a {adj1} {teaching_adj_str} tutor for the course '{course_title}'.

# {activity_context_str}Your name is SIMBA 😸 (Sistema Inteligente de Medición, Bienestar y Apoyo) and you were created by the Núcleo Milenio de Educación Superior and IRIT Talent team.
# Respond in a {adj1}, concise and proactive way{emojis_str}

# Help the student answer the following questions:

# {questions_str}

# {subjects_str}

# {answers_text} {teaching_type_text}

# {documents_str}

# Your first message should begin with 'Hello! 😸 I am SIMBA, and I will help you reflect on the following questions: ' Followed by the questions to answer.

# {limits_str}{files_str}"""

#     system_prompt = full_template.strip()
    
#     if expert_mode and custom_prompt:
#         system_prompt += f"\n\n{custom_prompt}"

#     if not allow_bot_questions:
#         system_prompt += "\n\nDo not provide questions to the student unless explicitly asked."
    
#     return system_prompt

# The Assistants API was shut down on Aug 26, 2026. Activity documents now live in a
# vector store that the chat searches with the Responses API `file_search` tool
# (see chainlit_app.py), so there is no assistant object to create or update.

def _upload_files(vector_store_id: str, files: List[Dict[str, Any]]) -> None:
    """Upload files and wait until the vector store has indexed them."""
    for file_data in files:
        file_content = base64.b64decode(file_data['content'])

        # Passing (filename, bytes) keeps the teacher's original filename
        file_obj = client.files.create(
            file=(file_data['filename'], file_content),
            purpose="assistants"
        )

        vs_file = client.vector_stores.files.create_and_poll(
            vector_store_id=vector_store_id,
            file_id=file_obj.id
        )
        if vs_file.status != 'completed':
            raise RuntimeError(f"Indexing {file_data['filename']} failed: {vs_file.last_error}")

def create_activity_documents(activity_data: Dict[str, Any], files: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a vector store holding an activity's documents. No files -> no vector store."""
    vector_store_id = None
    try:
        if files:
            vector_store = client.vector_stores.create(
                name=f"Activity: {activity_data.get('title', 'Untitled')}"
            )
            vector_store_id = vector_store.id
            _upload_files(vector_store_id, files)

        return {
            'vector_store_id': vector_store_id,
            'success': True
        }

    except Exception as e:
        logger.error(f"Error creating activity documents: {str(e)}")
        if vector_store_id:
            delete_activity_documents(vector_store_id)
        return {
            'vector_store_id': None,
            'success': False,
            'error': str(e)
        }

def add_activity_documents(vector_store_id: Optional[str], activity_data: Dict[str, Any], files: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Add files to an activity's vector store, creating the store if it doesn't exist yet."""
    if not vector_store_id:
        return create_activity_documents(activity_data, files)
    try:
        if files:
            _upload_files(vector_store_id, files)
        return {
            'vector_store_id': vector_store_id,
            'success': True
        }

    except Exception as e:
        logger.error(f"Error adding activity documents: {str(e)}")
        return {
            'vector_store_id': vector_store_id,
            'success': False,
            'error': str(e)
        }

def delete_activity_documents(vector_store_id: str) -> Dict[str, Any]:
    """Delete an activity's vector store and the files in it."""
    try:
        files = client.vector_stores.files.list(vector_store_id=vector_store_id)

        for file in files:
            try:
                client.files.delete(file.id)
            except Exception as e:
                logger.warning(f"Could not delete file {file.id}: {str(e)}")

        client.vector_stores.delete(vector_store_id)

        return {
            'success': True
        }

    except Exception as e:
        logger.warning(f"Could not delete vector store {vector_store_id}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_assistant_files(vector_store_id: str) -> List[Dict[str, Any]]:
    """Get list of files associated with an assistant's vector store"""
    try:
        if not vector_store_id:
            return []
        
        files = client.vector_stores.files.list(vector_store_id=vector_store_id)
        result = []
        
        for file in files:
            try:
                file_obj = client.files.retrieve(file.id)
                result.append({
                    'id': file.id,
                    'filename': file_obj.filename,
                    'size': file_obj.bytes,
                    'created_at': datetime.fromtimestamp(file_obj.created_at)
                })
            except Exception as e:
                logger.warning(f"Could not retrieve file info for {file.id}: {str(e)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting assistant files: {str(e)}")
        return []

def delete_assistant_file(vector_store_id: str, file_id: str) -> Dict[str, Any]:
    """Delete a specific file from an assistant's vector store"""
    try:
        client.vector_stores.files.delete(
            vector_store_id=vector_store_id,
            file_id=file_id
        )
        
        client.files.delete(file_id)
        
        return {
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error deleting assistant file: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def upload_file_to_assistant(vector_store_id: str, file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Upload a new file to an existing assistant's vector store"""
    try:
        file_content = base64.b64decode(file_data['content'])

        file_obj = client.files.create(
            file=(file_data['filename'], file_content),
            purpose="assistants"
        )

        vs_file = client.vector_stores.files.create_and_poll(
            vector_store_id=vector_store_id,
            file_id=file_obj.id
        )
        if vs_file.status != 'completed':
            raise RuntimeError(f"Indexing failed: {vs_file.last_error}")

        return {
            'success': True,
            'file_id': file_obj.id,
            'filename': file_obj.filename,
            'size': file_obj.bytes
        }
            
    except Exception as e:
        logger.error(f"Error uploading file to assistant: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        } 