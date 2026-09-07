import os
import base64
import tempfile
from datetime import datetime
from openai import OpenAI, NotFoundError
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

def create_assistant(activity_data: Dict[str, Any], files: List[Dict[str, Any]] = None, language: str = "en") -> Dict[str, Any]:
    """Create a new OpenAI assistant for an activity"""
    try:
        instructions = build_system_prompt(activity_data, logger, language)
        
        vector_store_id = None
        if files:
            vector_store = client.vector_stores.create(
                name=f"Activity: {activity_data.get('title', 'Untitled')}"
            )
            vector_store_id = vector_store.id
            
            for file_data in files:
                file_content = base64.b64decode(file_data['content'])
                
                with tempfile.NamedTemporaryFile(
                    suffix=f"_{file_data['filename']}", 
                    delete=False
                ) as temp_file:
                    temp_file.write(file_content)
                    temp_file_path = temp_file.name
                
                try:
                    with open(temp_file_path, 'rb') as f:
                        file_obj = client.files.create(
                            file=f,
                            purpose="assistants"
                        )
                    
                    client.vector_stores.files.create(
                        vector_store_id=vector_store_id,
                        file_id=file_obj.id
                    )
                    
                finally:
                    os.unlink(temp_file_path)
        
        tool_resources = {}
        if vector_store_id:
            tool_resources = {"file_search": {"vector_store_ids": [vector_store_id]}}
        
        metadata = {}
        if activity_data.get('start_date'):
            metadata['startDate'] = activity_data['start_date'].strftime("%Y/%m/%d")
        if activity_data.get('end_date'):
            metadata['endDate'] = activity_data['end_date'].strftime("%Y/%m/%d")
        
        assistant = client.beta.assistants.create(
            name=activity_data.get('title', 'SIMBA Activity'),
            description=activity_data.get('description', ''),
            instructions=instructions,
            tools=[{"type": "file_search"}],
            model="gpt-4o-mini",
            tool_resources=tool_resources,
            metadata=metadata
        )
        
        return {
            'assistant_id': assistant.id,
            'vector_store_id': vector_store_id,
            'success': True
        }
        
    except Exception as e:
        detail = getattr(e, 'body', None) or getattr(e, 'message', None) or str(e)
        logger.error(f"Error creating OpenAI assistant: {str(e)} | detail={detail}")
        return {
            'assistant_id': None,
            'vector_store_id': None,
            'success': False,
            'error': str(e)
        }

def update_assistant(assistant_id: str, activity_data: Dict[str, Any], files: List[Dict[str, Any]] = None, language = "en") -> Dict[str, Any]:
    """Update an existing OpenAI assistant"""
    try:
        assistant = client.beta.assistants.retrieve(assistant_id)
    except NotFoundError:
        # L'assistant stocké en base n'existe plus sous la clé API actuellement
        # configurée (clé changée/tournée entre environnements, ou assistant
        # supprimé côté OpenAI). Plutôt que d'échouer la mise à jour, on
        # recrée un assistant neuf avec les mêmes réglages, et on renvoie son
        # nouvel id pour que l'appelant (update_activity_api) le sauvegarde.
        logger.warning(
            f"OpenAI assistant {assistant_id} introuvable (404) sous la clé API "
            f"actuelle — recréation d'un nouvel assistant pour cette activité."
        )
        return create_assistant(activity_data, files, language)

    try:
        vector_store_id = None
        if hasattr(assistant.tool_resources, 'file_search') and assistant.tool_resources.file_search:
            if assistant.tool_resources.file_search.vector_store_ids:
                vector_store_id = assistant.tool_resources.file_search.vector_store_ids[0]
        

        instructions = build_system_prompt(activity_data, logger, language)
        
        if files:
            if not vector_store_id:
                vector_store = client.vector_stores.create(
                    name=f"Activity: {activity_data.get('title', 'Untitled')}"
                )
                vector_store_id = vector_store.id
            
            for file_data in files:
                file_content = base64.b64decode(file_data['content'])
                
                with tempfile.NamedTemporaryFile(
                    suffix=f"_{file_data['filename']}", 
                    delete=False
                ) as temp_file:
                    temp_file.write(file_content)
                    temp_file_path = temp_file.name
                
                try:
                    with open(temp_file_path, 'rb') as f:
                        file_obj = client.files.create(
                            file=f,
                            purpose="assistants"
                        )
                    
                    client.vector_stores.files.create(
                        vector_store_id=vector_store_id,
                        file_id=file_obj.id
                    )
                    
                finally:
                    os.unlink(temp_file_path)
        
        metadata = {}
        if activity_data.get('start_date'):
            metadata['startDate'] = activity_data['start_date'].strftime("%Y/%m/%d")
        if activity_data.get('end_date'):
            metadata['endDate'] = activity_data['end_date'].strftime("%Y/%m/%d")
        
        tool_resources = {}
        if vector_store_id:
            tool_resources = {"file_search": {"vector_store_ids": [vector_store_id]}}
        
        updated_assistant = client.beta.assistants.update(
            assistant_id=assistant_id,
            name=activity_data.get('title', 'SIMBA Activity'),
            description=activity_data.get('description', ''),
            instructions=instructions,
            tool_resources=tool_resources,
            metadata=metadata
        )
        
        return {
            'assistant_id': updated_assistant.id,
            'vector_store_id': vector_store_id,
            'success': True
        }
        
    except NotFoundError:
        # Le retrieve() initial a réussi mais l'update() échoue en 404 (rare,
        # ex. assistant supprimé entre les deux appels) — même filet de
        # sécurité : on recrée plutôt que d'échouer.
        logger.warning(
            f"OpenAI assistant {assistant_id} disparu pendant la mise à jour — "
            f"recréation d'un nouvel assistant pour cette activité."
        )
        return create_assistant(activity_data, files, language)
    except Exception as e:
        detail = getattr(e, 'body', None) or getattr(e, 'message', None) or str(e)
        logger.error(f"Error updating OpenAI assistant: {str(e)} | detail={detail}")
        return {
            'assistant_id': None,
            'vector_store_id': None,
            'success': False,
            'error': str(e)
        }

def delete_assistant(assistant_id: str, vector_store_id: str = None) -> Dict[str, Any]:
    """Delete an OpenAI assistant and its associated resources"""
    try:
        if vector_store_id:
            try:
                files = client.vector_stores.files.list(vector_store_id=vector_store_id)
                
                for file in files:
                    try:
                        client.files.delete(file.id)
                    except Exception as e:
                        logger.warning(f"Could not delete file {file.id}: {str(e)}")
                
                client.vector_stores.delete(vector_store_id)
                
            except Exception as e:
                logger.warning(f"Could not delete vector store {vector_store_id}: {str(e)}")
        
        client.beta.assistants.delete(assistant_id)
        
        return {
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error deleting OpenAI assistant: {str(e)}")
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
        
        with tempfile.NamedTemporaryFile(
            suffix=f"_{file_data['filename']}", 
            delete=False
        ) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        try:
            with open(temp_file_path, 'rb') as f:
                file_obj = client.files.create(
                    file=f,
                    purpose="assistants"
                )
            
            client.vector_stores.files.create(
                vector_store_id=vector_store_id,
                file_id=file_obj.id
            )
            
            return {
                'success': True,
                'file_id': file_obj.id,
                'filename': file_obj.filename,
                'size': file_obj.bytes
            }
            
        finally:
            os.unlink(temp_file_path)
            
    except Exception as e:
        logger.error(f"Error uploading file to assistant: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }