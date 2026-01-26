"""Service for extracting and formatting conversation transcripts from LiveKit ChatContext."""
import logging
import json
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class TranscriptService:
    """
    Extract and normalize conversation transcripts from LiveKit ChatContext.
    
    Methods:
    - extract_from_chat_context(): Parse chat items into normalized format
    - format_for_display(): Format messages as human-readable transcript
    
    Handles: user/assistant messages, function calls, outputs, embedded tool calls
    """
    
    @staticmethod
    def extract_from_chat_context(chat_items: List) -> List[Dict[str, Any]]:
        """
        Parse LiveKit chat items into normalized message format.
        
        Args:
            chat_items: List from session._chat_ctx.items
            
        Returns:
            List of dicts with role, content/name/params/result, timestamp
        """
        messages = []
        
        for item in chat_items:
            item_type = type(item).__name__
            
            # Handle function calls
            if item_type == "FunctionCall":
                try:
                    tool_name = getattr(item, 'tool_name', getattr(item, 'name', 'unknown'))
                    raw_arguments = getattr(item, 'arguments', getattr(item, 'raw_arguments', ''))
                    
                    args_dict = {}
                    if isinstance(raw_arguments, str) and raw_arguments.strip():
                        try:
                            args_dict = json.loads(raw_arguments)
                        except:
                            pass
                    
                    messages.append({
                        "role": "function",
                        "name": tool_name,
                        "params": args_dict,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception:
                    pass
                continue
            
            # Handle function outputs
            if item_type == "FunctionCallOutput":
                try:
                    content = getattr(item, 'content', getattr(item, 'output', ''))
                    if isinstance(content, list):
                        content = ' '.join(str(c) for c in content if c)
                    else:
                        content = str(content) if content else ""
                    
                    if messages and messages[-1]["role"] == "function":
                        messages[-1]["result"] = content.strip()
                except Exception:
                    pass
                continue
            
            # Handle regular messages
            if not hasattr(item, 'role'):
                continue
            
            role = item.role
            
            # Skip system messages
            if role == "system":
                continue
            
            # Handle tool results
            if role == "tool":
                content = getattr(item, 'content', '')
                if isinstance(content, list):
                    content = ' '.join(str(c) for c in content if c)
                else:
                    content = str(content) if content else ""
                
                if messages and messages[-1]["role"] == "function":
                    messages[-1]["result"] = content.strip()
                continue
            
            # Handle user and assistant messages
            if role in ["user", "assistant"]:
                content = getattr(item, 'content', '')
                
                if isinstance(content, list):
                    content = ' '.join(str(c) for c in content if c)
                else:
                    content = str(content) if content else ""
                
                if content.strip():
                    messages.append({
                        "role": role,
                        "content": content.strip(),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                # Handle embedded tool calls
                if role == "assistant" and hasattr(item, 'tool_calls') and item.tool_calls:
                    for tool_call in item.tool_calls:
                        tool_name = getattr(tool_call, 'function', {}).get('name', 'unknown') if hasattr(tool_call, 'function') else 'unknown'
                        tool_args = getattr(tool_call, 'function', {}).get('arguments', '') if hasattr(tool_call, 'function') else ''
                        
                        args_dict = {}
                        if isinstance(tool_args, str) and tool_args.strip():
                            try:
                                args_dict = json.loads(tool_args)
                            except:
                                pass
                        
                        messages.append({
                            "role": "function",
                            "name": tool_name,
                            "params": args_dict,
                            "timestamp": datetime.utcnow().isoformat()
                        })
        
        return messages
    
    @staticmethod
    def format_for_display(messages: List[Dict[str, Any]]) -> str:
        """
        Format messages into human-readable transcript.
        
        Args:
            messages: Normalized message dicts
            
        Returns:
            Multi-line transcript string with role labels
        """
        lines = ["===== CONVERSATION TRANSCRIPT =====\n"]
        
        for msg in messages:
            if msg["role"] == "user":
                lines.append(f"User: {msg['content']}")
            elif msg["role"] == "assistant":
                lines.append(f"Assistant: {msg['content']}")
            elif msg["role"] == "function":
                tool_name = msg.get("name", "unknown")
                params = msg.get("params", {})
                result = msg.get("result", "")
                
                params_str = ", ".join(f"{k}={v}" for k, v in params.items()) if params else ""
                lines.append(f"[TOOL CALL] {tool_name}({params_str})")
                
                if result:
                    lines.append(f"[TOOL RESULT] {result}")
        
        lines.append("\n===================================")
        return "\n".join(lines)
