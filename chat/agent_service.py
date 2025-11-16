"""
Service de l'Agent Intelligent
Gère l'interaction avec le LLM et l'exécution des outils
"""
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from groq import Groq
import json
import time

from .models import Conversation, Message, GeneratedFile, ConversationDocument
from .document_tools_service import DocumentToolsService
from documents.models import Document


class AgentService:
    """
    Service principal de l'agent LLM intelligent
    """

    # Définition des outils disponibles pour l'agent
    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "compare_documents",
                "description": "Compare deux ou plusieurs documents et identifie les différences, similitudes ou changements",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Liste des IDs des documents à comparer (2 minimum)"
                        },
                        "comparison_type": {
                            "type": "string",
                            "enum": ["differences", "similarities", "full"],
                            "description": "Type de comparaison: 'differences' (différences uniquement), 'similarities' (similitudes), 'full' (analyse complète)"
                        }
                    },
                    "required": ["document_ids"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "merge_documents",
                "description": "Fusionne deux documents en appliquant les modifications du document source vers le document cible",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_doc_id": {
                            "type": "integer",
                            "description": "ID du document source (qui contient les modifications)"
                        },
                        "target_doc_id": {
                            "type": "integer",
                            "description": "ID du document cible (qui sera modifié)"
                        },
                        "merge_strategy": {
                            "type": "string",
                            "enum": ["keep_latest", "manual", "smart"],
                            "description": "Stratégie de fusion: 'keep_latest' (garder les valeurs les plus récentes), 'manual' (demander confirmation), 'smart' (fusion intelligente)"
                        }
                    },
                    "required": ["source_doc_id", "target_doc_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "generate_pdf_document",
                "description": "Génère un document PDF personnalisé basé sur des instructions et optionnellement sur des documents sources",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Titre du document à générer"
                        },
                        "content": {
                            "type": "string",
                            "description": "Contenu du document (peut inclure du texte formaté, tableaux en markdown, etc.)"
                        },
                        "template": {
                            "type": "string",
                            "enum": ["report", "specification", "comparison", "custom"],
                            "description": "Type de template: 'report' (rapport), 'specification' (spécification technique), 'comparison' (comparaison), 'custom' (personnalisé)"
                        },
                        "source_docs": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "IDs des documents sources utilisés pour générer ce document"
                        }
                    },
                    "required": ["title", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "answer_question",
                "description": "Répond à une question en analysant le contenu d'un ou plusieurs documents. Utilise ce tool pour toute question nécessitant l'analyse du contenu des documents (informations, résumés, explications, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "La question de l'utilisateur"
                        },
                        "document_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "IDs des documents à analyser pour répondre (laisser vide pour utiliser tous les documents de la conversation)"
                        }
                    },
                    "required": ["question"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "edit_document",
                "description": "Modifie un élément spécifique dans un document (remplacer du texte, changer une valeur, corriger une erreur). Le document modifié sera automatiquement mis à jour et visible en temps réel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "integer",
                            "description": "ID du document à modifier"
                        },
                        "find_text": {
                            "type": "string",
                            "description": "Le texte exact à trouver et remplacer dans le document"
                        },
                        "replace_with": {
                            "type": "string",
                            "description": "Le nouveau texte qui remplacera l'ancien"
                        },
                        "context": {
                            "type": "string",
                            "description": "Contexte optionnel pour aider à localiser le texte (ex: 'dans le tableau des spécifications', 'dans la section dosage')"
                        }
                    },
                    "required": ["document_id", "find_text", "replace_with"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "format_text",
                "description": "Modifie le formatage (style) d'un texte spécifique dans l'éditeur (ajouter/retirer le gras, italique, changer la couleur, etc.). Utilise cet outil pour les commandes comme 'enlève le gras', 'mets en italique', 'change la couleur', etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "document_id": {
                            "type": "integer",
                            "description": "ID du document à modifier"
                        },
                        "text_to_format": {
                            "type": "string",
                            "description": "Le texte exact dont on veut modifier le formatage"
                        },
                        "formatting_action": {
                            "type": "string",
                            "enum": ["add_bold", "remove_bold", "add_italic", "remove_italic", "set_color", "remove_color", "set_size", "remove_all_formatting"],
                            "description": "L'action de formatage à effectuer: 'add_bold' (ajouter gras), 'remove_bold' (enlever gras), 'add_italic' (ajouter italique), 'remove_italic' (enlever italique), 'set_color' (changer couleur), 'remove_color' (enlever couleur), 'set_size' (changer taille), 'remove_all_formatting' (tout retirer)"
                        },
                        "formatting_value": {
                            "type": "string",
                            "description": "Valeur optionnelle pour l'action (ex: '#FF0000' pour la couleur rouge, '18px' pour la taille). Requis pour 'set_color' et 'set_size'"
                        }
                    },
                    "required": ["document_id", "text_to_format", "formatting_action"]
                }
            }
        }
    ]

    @staticmethod
    def process_message(conversation_id: int, user_message: str) -> Dict:
        """
        Traite un message utilisateur avec l'agent intelligent

        Args:
            conversation_id: ID de la conversation
            user_message: Message de l'utilisateur

        Returns:
            Dict avec la réponse de l'agent et les fichiers générés
        """
        start_time = time.time()

        try:
            conversation = Conversation.objects.get(id=conversation_id)

            # Récupérer le contexte de la conversation
            context = AgentService._get_conversation_context(conversation)

            print(f"[AGENT] Traitement du message: '{user_message[:50]}...'")
            print(f"[AGENT] Contexte: {len(context['documents'])} documents attachés")

            # Sauvegarder le message utilisateur
            user_msg = Message.objects.create(
                conversation=conversation,
                role='user',
                content=user_message
            )

            # Appeler le LLM avec les outils disponibles
            response_data = AgentService._call_llm_with_tools(
                conversation=conversation,
                user_message=user_message,
                context=context
            )

            # Traiter la réponse
            assistant_content = response_data.get('content', '')
            tools_used = response_data.get('tools_used', [])
            generated_files = response_data.get('generated_files', [])
            tokens_used = response_data.get('tokens_used', 0)

            # Sauvegarder la réponse de l'assistant
            assistant_msg = Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=assistant_content,
                tokens_used=tokens_used,
                response_time=time.time() - start_time
            )

            # Associer les fichiers générés au message
            for gen_file in generated_files:
                gen_file.message = assistant_msg
                gen_file.save()

            print(f"[AGENT] Réponse générée en {time.time() - start_time:.2f}s")
            print(f"[AGENT] Outils utilisés: {tools_used}")
            print(f"[AGENT] Fichiers générés: {len(generated_files)}")

            return {
                'success': True,
                'message': assistant_msg,
                'content': assistant_content,
                'generated_files': generated_files,
                'tools_used': tools_used,
                'tokens_used': tokens_used,
                'response_time': time.time() - start_time
            }

        except Conversation.DoesNotExist:
            return {
                'success': False,
                'error': 'Conversation non trouvée'
            }
        except Exception as e:
            print(f"[AGENT ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def _get_conversation_context(conversation: Conversation) -> Dict:
        """
        Récupère le contexte complet de la conversation

        Returns:
            Dict avec documents, historique, etc.
        """
        # Documents attachés à la conversation
        attached_docs = conversation.documents.all()

        # Documents via ConversationDocument (avec rôles)
        conversation_docs = ConversationDocument.objects.filter(
            conversation=conversation
        ).select_related('document')

        # Historique des messages (limité aux 10 derniers)
        messages = conversation.messages.order_by('-created_at')[:10]
        messages = list(reversed(messages))  # Plus ancien en premier

        # Fichiers générés dans cette conversation
        generated_files = GeneratedFile.objects.filter(
            conversation=conversation
        ).order_by('-generated_at')[:5]

        return {
            'documents': list(attached_docs),
            'conversation_documents': list(conversation_docs),
            'messages': messages,
            'generated_files': list(generated_files)
        }

    @staticmethod
    def _call_llm_with_tools(
        conversation: Conversation,
        user_message: str,
        context: Dict
    ) -> Dict:
        """
        Appelle le LLM avec function calling pour exécuter des outils si nécessaire
        """
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY n'est pas configurée")

        client = Groq(api_key=settings.GROQ_API_KEY)

        # Construire les messages pour le LLM
        messages = AgentService._build_messages(user_message, context, conversation)

        print(f"[AGENT] Appel du LLM avec {len(messages)} messages et {len(AgentService.TOOLS)} outils")

        # Premier appel au LLM
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            tools=AgentService.TOOLS,
            tool_choice="auto",  # Laisse le modèle décider
            temperature=0.5,
            max_tokens=2000
        )

        response_message = response.choices[0].message
        tokens_used = response.usage.total_tokens
        tools_used = []
        generated_files = []

        # Vérifier si le modèle veut appeler des outils
        tool_calls = response_message.tool_calls

        if tool_calls:
            print(f"[AGENT] Le modèle veut appeler {len(tool_calls)} outil(s)")

            # Ajouter la réponse du modèle aux messages
            messages.append(response_message)

            # Exécuter chaque outil demandé
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                print(f"[AGENT] Exécution de l'outil: {function_name}")
                print(f"[AGENT] Arguments: {function_args}")

                # Exécuter l'outil
                tool_result = AgentService._execute_tool(
                    tool_name=function_name,
                    tool_params=function_args,
                    conversation=conversation,
                    context=context
                )

                tools_used.append(function_name)

                # Ajouter les fichiers générés
                if 'generated_file' in tool_result and tool_result['generated_file'] is not None:
                    generated_files.append(tool_result['generated_file'])
                    # Remplacer l'objet GeneratedFile par son ID pour la sérialisation JSON
                    tool_result_serializable = tool_result.copy()
                    tool_result_serializable['generated_file_id'] = tool_result['generated_file'].id
                    del tool_result_serializable['generated_file']
                else:
                    # Pas de fichier généré ou None, on retire la clé
                    tool_result_serializable = tool_result.copy()
                    if 'generated_file' in tool_result_serializable:
                        del tool_result_serializable['generated_file']

                # Ajouter le résultat de l'outil aux messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps(tool_result_serializable, ensure_ascii=False)
                })

            # Deuxième appel au LLM avec les résultats des outils
            print(f"[AGENT] Deuxième appel au LLM avec les résultats des outils")

            second_response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=messages,
                temperature=0.5,
                max_tokens=2000
            )

            final_content = second_response.choices[0].message.content
            tokens_used += second_response.usage.total_tokens

        else:
            # Pas d'appel d'outil, réponse directe
            final_content = response_message.content

        return {
            'content': final_content,
            'tools_used': tools_used,
            'generated_files': generated_files,
            'tokens_used': tokens_used
        }

    @staticmethod
    def _build_messages(user_message: str, context: Dict, conversation) -> List[Dict]:
        """
        Construit les messages pour le LLM avec le contexte
        """
        messages = []

        # Message système avec instructions
        system_content = """Tu es un assistant intelligent spécialisé dans l'analyse de documents pharmaceutiques et techniques.

Tu as accès à plusieurs outils :
- answer_question : Pour répondre aux questions sur le contenu des documents (utilise cet outil pour TOUTE question nécessitant l'analyse des documents)
- edit_document : Pour modifier le CONTENU d'un document (remplacer du texte, changer une valeur, corriger une erreur)
- format_text : Pour modifier le FORMATAGE/STYLE d'un texte (ajouter/enlever gras, italique, changer couleur, taille, etc.)
- compare_documents : Pour comparer des documents et identifier les différences
- merge_documents : Pour fusionner des documents avec les modifications
- generate_pdf_document : Pour créer des documents PDF personnalisés

IMPORTANT - Distinction edit_document vs format_text :
- edit_document = Pour REMPLACER du texte (ex: "remplace X par Y", "change 2025 en 2026")
- format_text = Pour modifier le STYLE (ex: "enlève le gras", "mets en italique", "change la couleur en rouge")

Exemples de commandes de formatage (utilise format_text) :
- "enlève le gras sur S 20098" → format_text avec action='remove_bold'
- "mets en italique le titre" → format_text avec action='add_italic'
- "change la couleur de 'Important' en rouge" → format_text avec action='set_color', value='#FF0000'
- "retire tout le formatage sur ce paragraphe" → format_text avec action='remove_all_formatting'

AUTRES RÈGLES :
- Pour toute question sur le contenu d'un document, utilise TOUJOURS l'outil answer_question
- ATTENTION : Les modifications edit_document s'appliquent au document ORIGINAL (génère un nouveau PDF)
- Les modifications format_text s'appliquent au brouillon de l'éditeur (visible en temps réel dans l'éditeur)
- Quand tu reçois une réponse d'un outil, retransmets-la directement à l'utilisateur de manière claire et professionnelle
"""

        # Ajouter les documents disponibles au contexte système
        if context['documents']:
            system_content += "\n\nDocuments disponibles :\n"
            for doc in context['documents']:
                system_content += f"- ID {doc.id}: {doc.title} ({doc.file_type})\n"

        # Ajouter les fichiers générés récents (dernières modifications)
        recent_files = GeneratedFile.objects.filter(
            conversation=conversation
        ).order_by('-generated_at')[:3]

        if recent_files.exists():
            system_content += "\n\nFichiers modifiés récemment (tu peux continuer à les modifier) :\n"
            for gen_file in recent_files:
                # Les fichiers modifiés gardent l'ID du document original
                # Extraire l'ID du document original si disponible
                system_content += f"- {gen_file.title} (utilise edit_document pour modifier à nouveau)\n"

        messages.append({
            "role": "system",
            "content": system_content
        })

        # Ajouter l'historique récent (max 5 messages pour ne pas surcharger)
        for msg in context['messages'][-5:]:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # Ajouter le message utilisateur actuel
        messages.append({
            "role": "user",
            "content": user_message
        })

        return messages

    @staticmethod
    def _execute_tool(
        tool_name: str,
        tool_params: Dict,
        conversation: Conversation,
        context: Dict
    ) -> Dict:
        """
        Exécute un outil spécifique
        """
        try:
            if tool_name == "compare_documents":
                return DocumentToolsService.compare_documents(
                    document_ids=tool_params.get('document_ids', []),
                    comparison_type=tool_params.get('comparison_type', 'full'),
                    conversation=conversation
                )

            elif tool_name == "merge_documents":
                return DocumentToolsService.merge_documents(
                    source_doc_id=tool_params.get('source_doc_id'),
                    target_doc_id=tool_params.get('target_doc_id'),
                    merge_strategy=tool_params.get('merge_strategy', 'smart'),
                    conversation=conversation
                )

            elif tool_name == "generate_pdf_document":
                return DocumentToolsService.generate_pdf_document(
                    title=tool_params.get('title'),
                    content=tool_params.get('content'),
                    template=tool_params.get('template', 'custom'),
                    source_docs=tool_params.get('source_docs', []),
                    conversation=conversation
                )

            elif tool_name == "answer_question":
                return DocumentToolsService.answer_question(
                    question=tool_params.get('question'),
                    document_ids=tool_params.get('document_ids', []),
                    conversation=conversation
                )

            elif tool_name == "edit_document":
                return DocumentToolsService.edit_document(
                    document_id=tool_params.get('document_id'),
                    find_text=tool_params.get('find_text'),
                    replace_with=tool_params.get('replace_with'),
                    context=tool_params.get('context', ''),
                    conversation=conversation
                )

            elif tool_name == "format_text":
                return DocumentToolsService.format_text(
                    document_id=tool_params.get('document_id'),
                    text_to_format=tool_params.get('text_to_format'),
                    formatting_action=tool_params.get('formatting_action'),
                    formatting_value=tool_params.get('formatting_value'),
                    conversation=conversation
                )

            else:
                return {
                    'success': False,
                    'error': f"Outil inconnu: {tool_name}"
                }

        except Exception as e:
            print(f"[AGENT TOOL ERROR] {tool_name}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e)
            }
