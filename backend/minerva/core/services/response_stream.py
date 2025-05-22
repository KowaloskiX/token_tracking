import json
from minerva.core.middleware.token_tracking import update_user_token_usage
from minerva.core.services.function_calls import FunctionHandler
from openai import OpenAI
from fastapi import BackgroundTasks

openai = OpenAI()
function_handler = FunctionHandler()

class StreamManager:
    def __init__(self, background_tasks: BackgroundTasks):
        self.background_tasks = background_tasks

def get_file_info(file_ids):
    files = []
    for file_id in file_ids:
        try:
            file = openai.files.retrieve(file_id)
            files.append({
                'file_id': file_id,
                'name': file.filename
            })
        except Exception as e:
            print(f"Error retrieving file {file_id}: {e}")
    return files

def serialize_event(event):
    try:
        if hasattr(event, 'data'):
            object_type = event.data.object if hasattr(event.data, 'object') else None
            match object_type:
                case 'thread.message':
                    if (hasattr(event.data, 'content') and 
                        event.data.content and 
                        hasattr(event.data, 'status') and 
                        event.data.status == 'completed'):
                        
                        for content_block in event.data.content:
                            if (hasattr(content_block, 'text') and 
                                hasattr(content_block.text, 'annotations')):
                                citations = []
                                file_ids = set()  # Use set to avoid duplicates
                                
                                # Get the original text
                                text = content_block.text.value

                                for annotation in content_block.text.annotations:
                                    if (hasattr(annotation, 'type') and 
                                        annotation.type == 'file_citation'):
                                        citations.append({
                                            'file_id': annotation.file_citation.file_id,
                                            'text': annotation.text,
                                            'start_index': annotation.start_index,
                                            'end_index': annotation.end_index
                                        })
                                        file_ids.add(annotation.file_citation.file_id)
                                        
                                        # Remove the citation text from the content
                                        text = text.replace(annotation.text, '')
                                
                                if citations:
                                    # Retrieve file information for all cited files
                                    files = get_file_info(list(file_ids))
                                    
                                    return {
                                        'type': 'file_citation',
                                        'data': {
                                            'message_id': event.data.id,
                                            'thread_id': event.data.thread_id,
                                            'content': text,  # Clean text without citations
                                            'citations': citations,
                                            'files': files  # Add the retrieved file information
                                        }
                                    }
                    
                    return {
                        'type': 'message_status',
                        'data': {
                            'status': event.event.split('.')[-1],
                            'message_id': event.data.id,
                            'thread_id': event.data.thread_id,
                            'role': event.data.role,
                            'created_at': event.data.created_at
                        }
                    }
                    
                case 'thread.message.delta':
                    if (hasattr(event.data, 'delta') and 
                        hasattr(event.data.delta, 'content') and 
                        event.data.delta.content):
                        for content_block in event.data.delta.content:
                            if (hasattr(content_block, 'type') and 
                                content_block.type == 'text' and 
                                hasattr(content_block, 'text')):
                                
                                text = content_block.text.value
                                annotations = []
                                
                                # Handle citations in delta
                                if (hasattr(content_block.text, 'annotations') and 
                                    content_block.text.annotations):
                                    for annotation in content_block.text.annotations:
                                        if (hasattr(annotation, 'type') and 
                                            annotation.type == 'file_citation'):
                                            annotations.append({
                                                'file_id': annotation.file_citation.file_id,
                                                'text': annotation.quote,
                                                'start_index': annotation.start_index,
                                                'end_index': annotation.end_index
                                            })
                                            
                                            # Remove the citation text
                                            text = text.replace(annotation.text, '')
                                
                                return {
                                    'type': 'text',
                                    'data': text,  # Clean text without citations
                                    'citations': annotations if annotations else None
                                }

                # Rest of the cases remain the same
                case 'thread.run.step.delta':
                    # Handle run step deltas (tool calls, file search)
                    if (hasattr(event.data, 'delta') and 
                        hasattr(event.data.delta, 'step_details')):
                        step_details = event.data.delta.step_details
                        
                        if (hasattr(step_details, 'tool_calls') and 
                            step_details.tool_calls):
                            for tool_call in step_details.tool_calls:
                                # Handle file search tool calls
                                if hasattr(tool_call, 'file_search'):
                                    results = []
                                    if hasattr(tool_call.file_search, 'results'):
                                        for result in tool_call.file_search.results:
                                            file_result = {
                                                'file_id': result.file_id,
                                                'file_name': result.file_name,
                                                'score': result.score,
                                                'content': []
                                            }
                                            if hasattr(result, 'content'):
                                                for content in result.content:
                                                    if hasattr(content, 'text'):
                                                        file_result['content'].append({
                                                            'text': content.text,
                                                            'type': content.type
                                                        })
                                            results.append(file_result)
                                    
                                    return {
                                        'type': 'file_search',
                                        'data': {
                                            'results': results,
                                            'ranking_options': tool_call.file_search.get('ranking_options', {})
                                        }
                                    }
                                
                                # Handle function calls
                                if hasattr(tool_call, 'function') and tool_call.function:
                                    function_name = getattr(tool_call.function, 'name', None)
                                    function_arguments = getattr(tool_call.function, 'arguments', None)
                                    if function_name:
                                        return {
                                            'type': 'function_call',
                                            'data': {
                                                'name': function_name,
                                                'arguments': function_arguments,
                                            }
                                        }
                
                case 'thread.run':
                    # Handle completion status and token usage
                    status = getattr(event.data, 'status', None)
                    
                    if status == 'completed':
                        if hasattr(event.data, 'usage'):
                            return {
                                'type': 'completion_metrics',
                                'data': {
                                    'status': 'completed',
                                    'thread_id': event.data.thread_id,
                                    'run_id': event.data.id,
                                    'usage': {
                                        'completion_tokens': event.data.usage.completion_tokens,
                                        'prompt_tokens': event.data.usage.prompt_tokens,
                                        'total_tokens': event.data.usage.total_tokens
                                    }
                                }
                            }
                    
                    elif status == 'in_progress':
                        run_id = event.data.id
                        return {
                            'type': 'run_in_progress',
                            'data': {
                                'run_id': run_id,
                                'thread_id': event.data.thread_id,
                                'started_at': event.data.started_at,
                            }
                        }
                    
                    elif status == 'failed':
                        run_id = event.data.id
                        return {
                            'type': 'run_failed',
                            'data': {
                                'run_id': run_id,
                                'thread_id': event.data.thread_id,
                                'failed_at': event.data.failed_at,
                                'last_error': {
                                    'code': event.data.last_error.code if event.data.last_error else None,
                                    'message': event.data.last_error.message if event.data.last_error else None
                                },
                                'instructions': event.data.instructions,
                                'model': event.data.model
                            }
                        }
                    
                    # Handle required actions (existing logic)
                    if (hasattr(event.data, 'required_action') and 
                        event.data.required_action):
                        tool_calls = []
                        for tool_call in event.data.required_action.submit_tool_outputs.tool_calls:
                            tool_calls.append({
                                'id': tool_call.id,
                                'thread_id': event.data.thread_id,
                                'run_id': event.data.id,
                                'function': {
                                    'name': tool_call.function.name,
                                    'arguments': tool_call.function.arguments
                                },
                            })
                        return {
                            'type': 'tool_action',
                            'data': tool_calls
                        }

    except Exception as e:
        print(f"Error processing the event: {e}")
    
    return None


def event_stream(openai_stream, user_id: str, stream_manager: StreamManager):
    buffer = ""
    inside_pattern = False

    try:
        for event in openai_stream:
            value = serialize_event(event)
            if value:
                # Handle completion metrics and update token usage
                if value['type'] == 'completion_metrics':
                    try:
                        total_tokens = value['data']['usage']['total_tokens']
                        stream_manager.background_tasks.add_task(
                            update_user_token_usage,
                            user_id,
                            total_tokens
                        )
                    except Exception as e:
                        print(f"Error scheduling token usage update: {e}")

                if value['type'] == 'text':
                    buffer += value['data']
                    while buffer:
                        if inside_pattern:
                            end_idx = buffer.find('】')
                            if end_idx == -1:
                                buffer = ""
                                break
                            else:
                                buffer = buffer[end_idx + 1:]
                                inside_pattern = False
                        else:
                            start_idx = buffer.find('【')
                            if start_idx == -1:
                                yield f"data: {json.dumps(value)}\n\n"
                                buffer = ""
                            else:
                                yield f"data: {json.dumps({'type': 'text', 'data': buffer[:start_idx]})}\n\n"
                                buffer = buffer[start_idx:]
                                inside_pattern = True
                                
                elif value['type'] in ['function_call', 'tool_action', 'file_search', 'message_status', 'file_citation', 'completion_metrics']:
                    yield f"data: {json.dumps(value)}\n\n"
                    
                    if value['type'] == 'tool_action':
                        if any(tool['function']['arguments'] and tool['function']['arguments'].strip() != '{}' for tool in value['data']):
                            tool_output, thread_id, run_id = function_handler.handle_function_call(value['data'])
                            if tool_output:
                                yield f"data: {json.dumps({'type': 'tool_outputs', 'data': tool_output})}\n\n"
                                yield from continue_streaming(thread_id, run_id, [tool_output], user_id)
    except Exception as e:
        print(str(e))
        yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

def continue_streaming(thread_id, run_id, tool_outputs, user_id: str):
    with openai.beta.threads.runs.submit_tool_outputs_stream(
        thread_id=thread_id,
        run_id=run_id,
        tool_outputs=tool_outputs,
    ) as stream:
        for event in stream:
            value = serialize_event(event)
            if value:
                yield f"data: {json.dumps(value)}\n\n"