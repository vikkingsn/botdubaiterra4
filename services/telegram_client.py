"""
Telegram Client для отправки сообщений от имени пользователя
"""
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.errors import (
    UserNotParticipant, ChatWriteForbidden, FloodWait,
    PeerIdInvalid, UsernameNotOccupied, UsernameInvalid,
    UserPrivacyRestricted, UserDeactivated, ChannelPrivate,
    ChatAdminRequired, InviteHashExpired, InviteHashInvalid,
    UserAlreadyParticipant, PeerFlood
)
from utils.logger import logger
from config import API_ID, API_HASH, PHONE_NUMBER
from typing import Optional, Dict, List
from database import crud
import asyncio

# Кеш клиентов для каждого пользователя
_clients: Dict[int, Client] = {}


async def get_user_client(user_id: int) -> Optional[Client]:
    """
    Получить Client API для конкретного пользователя
    
    Если у пользователя нет своих данных - использует общие из .env
    Авторизация происходит автоматически при первом использовании.
    """
    # Проверяем кеш
    if user_id in _clients:
        client = _clients[user_id]
        try:
            # Проверяем подключение безопасно
            if hasattr(client, 'is_connected') and client.is_connected:
                return client
        except Exception:
            # Если проверка не удалась, создаем новый клиент
            pass
    
    # Получаем данные пользователя из БД
    user = await crud.get_user_by_telegram_id(user_id)
    
    # Определяем какие данные использовать
    if user and user.has_client_auth and user.api_id and user.api_hash:
        # У пользователя есть свои данные - используем их
        api_id = user.api_id
        api_hash = user.api_hash
        phone = user.phone_number
        session_name = f"client_{user_id}"
        logger.info(f"Используем персональный Client API для пользователя {user_id}")
    else:
        # Используем общие данные из .env (для владельца бота)
        if not API_ID or not API_HASH:
            logger.warning(f"У пользователя {user_id} нет Client API и общие данные не настроены")
            return None
        
        api_id = API_ID
        api_hash = API_HASH
        phone = PHONE_NUMBER
        session_name = "mailing_client"  # Общая сессия для всех без персональной авторизации
        logger.info(f"Используем общий Client API для пользователя {user_id}")
    
    # Создаем клиент
    client = Client(
        session_name,
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone
    )
    
    # Авторизуемся автоматически
    try:
        # Всегда пытаемся запустить клиент (start() безопасен для уже запущенных)
        logger.info(f"🔐 Авторизация Client API для пользователя {user_id}...")
        logger.info(f"   Session: {session_name}, API_ID: {api_id}, Phone: {phone}")
        
        # Запускаем клиент
        # В Pyrogram 2.0.106 client.start() всегда возвращает корутину
        await client.start()
        
        logger.info(f"✅ Client API авторизован для пользователя {user_id}")
        
        # Если это персональная авторизация - обновляем статус в БД
        if user and not user.has_client_auth:
            try:
                await crud.update_user_client_auth(
                    telegram_id=user_id,
                    has_auth=True
                )
            except Exception as e:
                logger.warning(f"Не удалось обновить статус авторизации в БД: {e}")
        
        # Кешируем клиент
        _clients[user_id] = client
        return client
        
    except TypeError as e:
        # Специальная обработка для ошибки "can't be used in 'await' expression"
        if "can't be used in 'await' expression" in str(e):
            logger.error(f"❌ Ошибка: client.start() вернул None для {user_id}")
            logger.error(f"   Это может означать, что клиент уже запущен или сессия повреждена")
            # Пробуем использовать клиент напрямую
            try:
                _clients[user_id] = client
                return client
            except Exception as e2:
                logger.error(f"❌ Не удалось использовать клиент: {e2}")
                return None
        else:
            raise
    except Exception as e:
        logger.error(f"❌ Ошибка авторизации Client API для {user_id}: {e}", exc_info=True)
        return None


async def check_account_status(user_id: int) -> Dict:
    """
    Проверяет статус аккаунта перед началом рассылки
    Пытается отправить тестовое сообщение самому себе (Saved Messages)
    
    Returns:
        {
            "success": bool,
            "error_type": str | None,
            "error_details": str | None
        }
    """
    try:
        # Получаем клиент для пользователя
        client = await get_user_client(user_id)
        
        if client is None:
            return {
                "success": False,
                "error_type": "no_client",
                "error_details": "Client API не настроен"
            }
        
        # Пытаемся отправить тестовое сообщение самому себе (Saved Messages)
        # Это безопасный способ проверить, не ограничен ли аккаунт
        try:
            await client.send_message("me", "test")
            logger.info(f"✅ Проверка статуса аккаунта для {user_id}: аккаунт не ограничен")
            return {
                "success": True,
                "error_type": None,
                "error_details": None
            }
        except PeerFlood as e:
            logger.error(f"⚠️ PEER_FLOOD при проверке статуса аккаунта для {user_id}: {e}")
            return {
                "success": False,
                "error_type": "peer_flood",
                "error_details": "Аккаунт все еще ограничен Telegram (PEER_FLOOD). Ограничение может быть снято для Bot API, но еще активно для Client API. Подождите еще 1-2 часа."
            }
        except Exception as e:
            # Другие ошибки не критичны для проверки статуса
            logger.warning(f"Предупреждение при проверке статуса аккаунта для {user_id}: {e}")
            # Считаем, что проверка прошла (не PEER_FLOOD)
            return {
                "success": True,
                "error_type": None,
                "error_details": None
            }
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса аккаунта для {user_id}: {e}", exc_info=True)
        return {
            "success": False,
            "error_type": "unknown",
            "error_details": f"Ошибка при проверке статуса: {str(e)}"
        }


async def send_message_as_user(
    recipient_identifier: str,
    text: str,
    sender_user_id: int,
    media_type: Optional[str] = None,
    media_file_id: Optional[str] = None
) -> dict:
    """
    Отправляет сообщение от имени пользователя (не от бота)
    
    Сообщения отправляются от имени того, кто создал рассылку.
    Если у пользователя нет персонального Client API - используется общий из .env
    
    Args:
        recipient_identifier: @username или user_id получателя
        text: Текст сообщения
        sender_user_id: ID пользователя бота, от имени которого отправляется
    
    Returns:
        {
            "success": bool,
            "error_type": str,
            "error_details": str,
            "telegram_message_id": int | None
        }
    """
    try:
        # Получаем клиент для конкретного пользователя
        client = await get_user_client(sender_user_id)
        
        if client is None:
            # Если нет Client API - возвращаем ошибку
            return {
                "success": False,
                "error_type": "no_client",
                "error_details": "Client API не настроен. Настройте через /setup_my_client или используйте общие настройки в .env",
                "telegram_message_id": None
            }
        
        # Определяем получателя (может быть пользователь, группа или канал)
        chat_id = None
        
        if recipient_identifier.isdigit() or (recipient_identifier.startswith("-") and recipient_identifier[1:].isdigit()):
            # Это user_id или chat_id (может быть отрицательным для групп)
            chat_id = int(recipient_identifier)
        else:
            # Это username или ссылка на группу/канал
            original_identifier = recipient_identifier
            # Удаляем @ если есть
            identifier = recipient_identifier.lstrip("@")
            
            # Если это ссылка, извлекаем username/groupname или invite_hash
            if "t.me/" in identifier or "telegram.me/" in identifier:
                import re
                # Проверяем формат ссылки: t.me/joinchat/HASH или t.me/+HASH (для приватных групп)
                invite_match = re.search(r'(?:t\.me/|telegram\.me/)(?:joinchat/|\+)([a-zA-Z0-9_-]+)', identifier)
                if invite_match:
                    # Это invite-ссылка на приватную группу
                    invite_hash = invite_match.group(1)
                    try:
                        # Пытаемся присоединиться к группе по invite-ссылке
                        chat = await client.join_chat(f"https://t.me/joinchat/{invite_hash}")
                        chat_id = chat.id
                        logger.info(f"Присоединились к приватной группе по invite-ссылке: {chat_id}")
                    except (InviteHashExpired, InviteHashInvalid) as e:
                        logger.warning(f"Недействительная invite-ссылка для {original_identifier}: {e}")
                        return {
                            "success": False,
                            "error_type": "invalid_invite",
                            "error_details": f"Недействительная или истекшая invite-ссылка: {str(e)}",
                            "telegram_message_id": None
                        }
                    except Exception as e:
                        logger.warning(f"Не удалось присоединиться к группе по invite-ссылке {original_identifier}: {e}")
                        return {
                            "success": False,
                            "error_type": "join_failed",
                            "error_details": f"Не удалось присоединиться к группе: {str(e)}",
                            "telegram_message_id": None
                        }
                else:
                    # Обычная ссылка на публичную группу/канал
                    match = re.search(r'(?:t\.me/|telegram\.me/)(?:c/)?([a-zA-Z0-9_]+)', identifier)
                    if match:
                        chat_id = match.group(1)
                    else:
                        chat_id = identifier
            else:
                # Это просто username
                chat_id = identifier
        
        # Если chat_id - это строка (username), пытаемся получить chat объект для проверки
        if isinstance(chat_id, str):
            try:
                # Пытаемся получить информацию о чате
                chat = await client.get_chat(chat_id)
                chat_id = chat.id  # Используем числовой ID
                logger.debug(f"Получен chat_id {chat_id} для {recipient_identifier}")
            except (PeerIdInvalid, UsernameNotOccupied, UsernameInvalid, ChannelPrivate) as e:
                logger.warning(f"Не удалось получить информацию о чате {chat_id}: {e}")
                return {
                    "success": False,
                    "error_type": "invalid_user",
                    "error_details": f"Чат не найден или недоступен: {str(e)}",
                    "telegram_message_id": None
                }
            except Exception as e:
                logger.warning(f"Ошибка при получении информации о чате {chat_id}: {e}")
                # Продолжаем с username, возможно это публичная группа
                pass
        
        # Проверяем, является ли пользователь участником группы (для групп)
        if isinstance(chat_id, int) and chat_id < 0:
            # Это группа (chat_id отрицательный)
            try:
                # Проверяем, является ли пользователь участником
                chat_member = await client.get_chat_member(chat_id, "me")
                if chat_member.status not in ["member", "administrator", "creator"]:
                    logger.warning(f"Пользователь не является участником группы {chat_id}")
                    return {
                        "success": False,
                        "error_type": "not_participant",
                        "error_details": "Вы не являетесь участником этой группы. Присоединитесь к группе перед отправкой сообщений.",
                        "telegram_message_id": None
                    }
            except UserNotParticipant:
                logger.warning(f"Пользователь не является участником группы {chat_id}")
                return {
                    "success": False,
                    "error_type": "not_participant",
                    "error_details": "Вы не являетесь участником этой группы. Присоединитесь к группе перед отправкой сообщений.",
                    "telegram_message_id": None
                }
            except Exception as e:
                logger.warning(f"Ошибка при проверке участника группы {chat_id}: {e}")
                # Продолжаем попытку отправки
        
        # Отправляем сообщение (Pyrogram автоматически определит тип чата)
        # Если есть медиа, отправляем его с подписью, иначе просто текст
        if media_type and media_file_id:
            # Отправляем медиа с подписью
            if media_type == "photo":
                message = await client.send_photo(
                    chat_id=chat_id,
                    photo=media_file_id,
                    caption=text if text else None
                )
            elif media_type == "video":
                message = await client.send_video(
                    chat_id=chat_id,
                    video=media_file_id,
                    caption=text if text else None
                )
            elif media_type == "document":
                message = await client.send_document(
                    chat_id=chat_id,
                    document=media_file_id,
                    caption=text if text else None
                )
            elif media_type == "audio":
                message = await client.send_audio(
                    chat_id=chat_id,
                    audio=media_file_id,
                    caption=text if text else None
                )
            elif media_type == "voice":
                message = await client.send_voice(
                    chat_id=chat_id,
                    voice=media_file_id,
                    caption=text if text else None
                )
            elif media_type == "video_note":
                message = await client.send_video_note(
                    chat_id=chat_id,
                    video_note=media_file_id
                )
                # video_note не поддерживает caption, поэтому если есть текст, отправляем отдельно
                if text:
                    await client.send_message(chat_id=chat_id, text=text)
            elif media_type == "animation":
                message = await client.send_animation(
                    chat_id=chat_id,
                    animation=media_file_id,
                    caption=text if text else None
                )
            else:
                # Неизвестный тип медиа - отправляем как документ
                message = await client.send_document(
                    chat_id=chat_id,
                    document=media_file_id,
                    caption=text if text else None
                )
        else:
            # Отправляем просто текст
            message = await client.send_message(
                chat_id=chat_id,
                text=text
            )
        
        logger.info(f"Сообщение отправлено от имени пользователя получателю {recipient_identifier}, message_id: {message.id}")
        
        return {
            "success": True,
            "error_type": None,
            "error_details": None,
            "telegram_message_id": message.id
        }
    
    except FloodWait as e:
        # Нужно подождать
        wait_time = e.value
        logger.warning(f"FloodWait для {recipient_identifier}: нужно подождать {wait_time} секунд")
        await asyncio.sleep(wait_time)
        # Пробуем еще раз
        return await send_message_as_user(recipient_identifier, text, sender_user_id)
    
    except (PeerIdInvalid, UsernameNotOccupied, UsernameInvalid) as e:
        logger.warning(f"Неверный получатель {recipient_identifier}: {e}")
        return {
            "success": False,
            "error_type": "invalid_user",
            "error_details": f"Пользователь не найден: {str(e)}",
            "telegram_message_id": None
        }
    
    except ChatWriteForbidden:
        logger.warning(f"Нельзя писать получателю {recipient_identifier}: запрещено")
        return {
            "success": False,
            "error_type": "privacy",
            "error_details": "Нельзя отправить сообщение этому пользователю",
            "telegram_message_id": None
        }
    
    except UserPrivacyRestricted:
        logger.warning(f"Ограничения приватности для {recipient_identifier}")
        return {
            "success": False,
            "error_type": "privacy",
            "error_details": "Ограничения приватности пользователя",
            "telegram_message_id": None
        }
    
    except UserDeactivated:
        logger.warning(f"Аккаунт {recipient_identifier} деактивирован")
        return {
            "success": False,
            "error_type": "deleted",
            "error_details": "Аккаунт деактивирован",
            "telegram_message_id": None
        }
    
    except UserNotParticipant:
        logger.warning(f"Пользователь {recipient_identifier} не является участником группы/канала")
        return {
            "success": False,
            "error_type": "not_participant",
            "error_details": "Вы не являетесь участником этой группы/канала. Присоединитесь к группе перед отправкой сообщений.",
            "telegram_message_id": None
        }
    
    except ChatAdminRequired:
        logger.warning(f"Требуются права администратора для отправки в {recipient_identifier}")
        return {
            "success": False,
            "error_type": "admin_required",
            "error_details": "Требуются права администратора для отправки сообщений в эту группу/канал",
            "telegram_message_id": None
        }
    
    except ChannelPrivate:
        logger.warning(f"Приватный канал/группа {recipient_identifier} недоступен")
        return {
            "success": False,
            "error_type": "private_chat",
            "error_details": "Это приватная группа/канал. Используйте invite-ссылку для присоединения или убедитесь, что вы являетесь участником.",
            "telegram_message_id": None
        }
    
    except PeerFlood as e:
        # Аккаунт ограничен из-за слишком частых отправок
        logger.error(f"⚠️ PEER_FLOOD: Аккаунт ограничен из-за слишком частых отправок для {recipient_identifier}: {e}")
        return {
            "success": False,
            "error_type": "peer_flood",
            "error_details": "Аккаунт временно ограничен Telegram из-за слишком частых отправок. Увеличьте интервал между сообщениями (минимум 15-30 секунд) или подождите 1-2 часа перед следующей рассылкой.",
            "telegram_message_id": None
        }
    
    except Exception as e:
        logger.error(f"Неизвестная ошибка при отправке {recipient_identifier}: {e}", exc_info=True)
        return {
            "success": False,
            "error_type": "unknown",
            "error_details": str(e),
            "telegram_message_id": None
        }


async def get_user_groups(user_id: int) -> List[Dict]:
    """
    Получить список всех групп и каналов пользователя
    
    Returns:
        List[Dict] с информацией о группах:
        [
            {
                "id": int,  # chat_id группы
                "title": str,  # название группы
                "type": str,  # "group", "supergroup", "channel"
                "username": str | None,  # username если есть
                "members_count": int  # количество участников
            },
            ...
        ]
    """
    try:
        client = await get_user_client(user_id)
        
        if client is None:
            logger.warning(f"Client API не настроен для пользователя {user_id}")
            return []
        
        groups = []
        
        # Получаем все диалоги (чаты)
        async for dialog in client.get_dialogs():
            # Фильтруем только группы и каналы
            if dialog.chat.type in ("group", "supergroup", "channel"):
                try:
                    # Получаем количество участников (упрощенный способ для производительности)
                    members_count = 0
                    try:
                        # Пытаемся получить информацию о чате
                        chat_info = await client.get_chat(dialog.chat.id)
                        if hasattr(chat_info, 'members_count') and chat_info.members_count:
                            members_count = chat_info.members_count
                        elif hasattr(dialog.chat, 'members_count') and dialog.chat.members_count:
                            members_count = dialog.chat.members_count
                    except Exception as e:
                        logger.debug(f"Не удалось получить количество участников для {dialog.chat.id}: {e}")
                        # Если не удалось получить, оставляем 0
                        members_count = 0
                    
                    groups.append({
                        "id": dialog.chat.id,
                        "title": dialog.chat.title or "Без названия",
                        "type": dialog.chat.type,
                        "username": dialog.chat.username,
                        "members_count": members_count
                    })
                except Exception as e:
                    logger.warning(f"Ошибка при обработке группы {dialog.chat.id}: {e}")
                    continue
        
        logger.info(f"Найдено {len(groups)} групп/каналов для пользователя {user_id}")
        return groups
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка групп для пользователя {user_id}: {e}", exc_info=True)
        return []


async def join_chat_by_link(user_id: int, invite_link: str) -> Dict:
    """
    Присоединиться к чату/группе/каналу по invite-ссылке
    
    Args:
        user_id: ID пользователя бота
        invite_link: Invite-ссылка на чат/группу/канал (https://t.me/joinchat/HASH, t.me/+HASH, или https://t.me/channelname)
    
    Returns:
        Dict с информацией о чате:
        {
            "success": bool,
            "chat_id": int | None,
            "title": str | None,
            "chat_type": str | None,  # "group", "supergroup", "channel"
            "error": str | None
        }
    """
    try:
        client = await get_user_client(user_id)
        
        if client is None:
            return {
                "success": False,
                "chat_id": None,
                "title": None,
                "chat_type": None,
                "error": "Client API не настроен"
            }
        
        # Нормализуем ссылку
        if not invite_link.startswith("http"):
            if invite_link.startswith("t.me/"):
                invite_link = f"https://{invite_link}"
            elif invite_link.startswith("+"):
                invite_link = f"https://t.me/joinchat/{invite_link.lstrip('+')}"
            else:
                invite_link = f"https://t.me/joinchat/{invite_link}"
        
        # Присоединяемся к чату/группе/каналу
        try:
            chat = await client.join_chat(invite_link)
            logger.info(f"Успешно присоединились к {chat.type} {chat.id} ({chat.title}) по ссылке")
            
            # Сохраняем в БД (если это бот)
            # Для пользователя чат будет в его списке диалогов
            
            return {
                "success": True,
                "chat_id": chat.id,
                "title": chat.title,
                "chat_type": chat.type,
                "error": None
            }
        except UserAlreadyParticipant:
            # Пользователь уже участник - пытаемся получить информацию о чате
            try:
                logger.info(f"Пользователь уже участник чата по ссылке {invite_link}")
                
                # Пытаемся получить информацию о чате через get_chat
                # Для invite-ссылок это может не сработать, но попробуем
                try:
                    # Извлекаем hash из invite-ссылки
                    import re
                    hash_match = re.search(r'joinchat/([a-zA-Z0-9_-]+)', invite_link)
                    if hash_match:
                        # Для invite-ссылок сложно получить chat_id напрямую
                        # Возвращаем успех с сообщением
                        return {
                            "success": True,
                            "chat_id": None,
                            "title": None,
                            "chat_type": None,
                            "error": None,
                            "message": "Вы уже являетесь участником этого чата. Чат доступен для использования в рассылках."
                        }
                    else:
                        # Если это не invite-ссылка, пытаемся получить информацию
                        # (хотя это не должно произойти в этом блоке)
                        return {
                            "success": True,
                            "chat_id": None,
                            "title": None,
                            "chat_type": None,
                            "error": None,
                            "message": "Вы уже являетесь участником этого чата"
                        }
                except Exception as e:
                    logger.warning(f"Не удалось обработать ссылку после UserAlreadyParticipant: {e}")
                    return {
                        "success": True,
                        "chat_id": None,
                        "title": None,
                        "chat_type": None,
                        "error": None,
                        "message": "Вы уже являетесь участником этого чата. Чат доступен для использования в рассылках."
                    }
            except Exception as e:
                logger.warning(f"Ошибка при обработке UserAlreadyParticipant: {e}")
                return {
                    "success": True,
                    "chat_id": None,
                    "title": None,
                    "chat_type": None,
                    "error": None,
                    "message": "Вы уже являетесь участником этого чата. Чат доступен для использования в рассылках."
                }
        except InviteHashExpired:
            return {
                "success": False,
                "chat_id": None,
                "title": None,
                "chat_type": None,
                "error": "Ссылка истекла или недействительна"
            }
        except InviteHashInvalid:
            return {
                "success": False,
                "chat_id": None,
                "title": None,
                "chat_type": None,
                "error": "Неверная ссылка на чат"
            }
        except Exception as e:
            logger.error(f"Ошибка при присоединении к чату по ссылке {invite_link}: {e}", exc_info=True)
            return {
                "success": False,
                "chat_id": None,
                "title": None,
                "chat_type": None,
                "error": f"Не удалось присоединиться: {str(e)}"
            }
    
    except Exception as e:
        logger.error(f"Ошибка при присоединении к чату: {e}", exc_info=True)
        return {
            "success": False,
            "chat_id": None,
            "title": None,
            "chat_type": None,
            "error": str(e)
        }


async def get_chat_info_by_link(user_id: int, chat_link: str) -> Dict:
    """
    Получить информацию о чате/группе/канале по ссылке (без присоединения)
    
    Args:
        user_id: ID пользователя бота
        chat_link: Ссылка на чат/группу/канал (https://t.me/groupname, @groupname, https://t.me/channelname)
    
    Returns:
        Dict с информацией о чате и участниках:
        {
            "success": bool,
            "chat_id": int | None,
            "title": str | None,
            "chat_type": str | None,  # "group", "supergroup", "channel"
            "members": List[int] | None,  # Только для групп/супергрупп
            "error": str | None
        }
    """
    try:
        client = await get_user_client(user_id)
        
        if client is None:
            return {
                "success": False,
                "chat_id": None,
                "title": None,
                "members": None,
                "error": "Client API не настроен"
            }
        
        # Нормализуем ссылку
        if chat_link.startswith("http"):
            # Извлекаем username из ссылки
            import re
            match = re.search(r'(?:t\.me/|telegram\.me/)(?:c/)?([a-zA-Z0-9_]+)', chat_link)
            if match:
                chat_username = match.group(1)
            else:
                return {
                    "success": False,
                    "chat_id": None,
                    "title": None,
                    "chat_type": None,
                    "members": None,
                    "error": "Неверный формат ссылки"
                }
        elif chat_link.startswith("@"):
            chat_username = chat_link[1:]
        else:
            chat_username = chat_link
        
        # Получаем информацию о чате
        try:
            chat = await client.get_chat(chat_username)
            
            # Логируем информацию о чате для отладки
            logger.info(f"Получена информация о чате: ID={chat.id}, Type={chat.type}, Title={chat.title}, Username={getattr(chat, 'username', None)}")
            
            # Получаем все доступные атрибуты для диагностики
            chat_attrs = {
                'type': chat.type,
                'is_broadcast': getattr(chat, 'is_broadcast', None),
                'is_group': getattr(chat, 'is_group', None),
                'is_supergroup': getattr(chat, 'is_supergroup', None),
                'is_channel': getattr(chat, 'is_channel', None),
            }
            logger.info(f"Атрибуты чата: {chat_attrs}")
            
            # Поддерживаем все типы чатов: группы, супергруппы, каналы
            # Проверяем более тщательно тип чата
            chat_type_raw = chat.type
            
            # В Pyrogram типы могут быть как строками, так и enum ChatType
            # Конвертируем enum в строку для единообразия
            if isinstance(chat_type_raw, ChatType):
                # Это enum ChatType, получаем строковое значение
                chat_type = chat_type_raw.value if hasattr(chat_type_raw, 'value') else str(chat_type_raw).split('.')[-1].lower()
            elif hasattr(chat_type_raw, 'name'):
                # Это может быть enum без value, используем name
                chat_type = chat_type_raw.name.lower()
            else:
                # Это уже строка
                chat_type = str(chat_type_raw).lower()
            
            logger.info(f"Тип чата (исходный): {chat_type_raw}, (обработанный): {chat_type}")
            
            # Проверяем тип чата
            if chat_type == "channel" or (isinstance(chat_type_raw, ChatType) and chat_type_raw == ChatType.CHANNEL):
                # Это канал
                chat_type = "channel"
                logger.info(f"✅ Определен как канал: {chat.id}")
            elif chat_type in ("group", "supergroup") or (isinstance(chat_type_raw, ChatType) and chat_type_raw in (ChatType.GROUP, ChatType.SUPERGROUP)):
                # Это группа или супергруппа
                logger.info(f"✅ Определен как {chat_type}: {chat.id}")
            else:
                # Пытаемся определить тип по дополнительным признакам
                logger.warning(f"Неожиданный тип чата: {chat_type} для {chat_username}, проверяем атрибуты...")
                
                # Проверяем атрибуты для определения типа
                if getattr(chat, 'is_broadcast', False) or getattr(chat, 'is_channel', False):
                    chat_type = "channel"
                    logger.info(f"Определен как канал по атрибутам is_broadcast/is_channel")
                elif getattr(chat, 'is_supergroup', False):
                    chat_type = "supergroup"
                    logger.info(f"Определен как супергруппа по атрибуту is_supergroup")
                elif getattr(chat, 'is_group', False):
                    chat_type = "group"
                    logger.info(f"Определен как группа по атрибуту is_group")
                else:
                    # Если все еще не определено, но чат существует - пробуем добавить как канал
                    # (возможно, это приватный канал, который определяется по-другому)
                    logger.warning(f"Не удалось точно определить тип, но чат существует. Пробуем обработать как канал/группу")
                    
                    # Для приватных каналов/групп тип может быть неопределен, но мы все равно можем их добавить
                    # Проверяем, есть ли у чата название (если есть - это скорее всего группа/канал)
                    if hasattr(chat, 'title') and chat.title:
                        # Пробуем определить по ID (каналы обычно имеют отрицательные ID с префиксом -100)
                        if chat.id < 0:
                            if abs(chat.id) >= 1000000000000:  # Каналы обычно имеют очень большие отрицательные ID
                                chat_type = "channel"
                                logger.info(f"Определен как канал по ID: {chat.id}")
                            else:
                                chat_type = "supergroup"
                                logger.info(f"Определен как супергруппа по ID: {chat.id}")
                        else:
                            chat_type = "group"
                            logger.info(f"Определен как группа по ID: {chat.id}")
                    else:
                        # Если нет названия - это скорее всего личный чат
                        logger.error(f"Чат не имеет названия, вероятно это личный чат или бот. Тип: {chat_type}")
                        return {
                            "success": False,
                            "chat_id": chat.id,
                            "title": None,
                            "chat_type": chat_type,
                            "members": None,
                            "error": f"Это не группа, супергруппа или канал. Тип: {chat_type}. Возможно, это личный чат или бот."
                        }
            
            # Получаем участников только для групп и супергрупп (не для каналов)
            members = None
            if chat_type in ("group", "supergroup"):
                logger.info(f"Пытаемся получить участников для {chat_type} {chat.id}")
                members = await get_group_members(user_id, chat.id)
                # Если не получилось через Pyrogram, пробуем Telethon
                if not members:
                    try:
                        logger.info(f"Пробуем получить участников через Telethon для {chat.id}")
                        members = await get_group_members(user_id, chat.id, use_telethon=True)
                    except Exception as e:
                        logger.warning(f"Не удалось использовать Telethon: {e}")
                
                if members:
                    logger.info(f"✅ Получено {len(members)} участников для {chat_type} {chat.id}")
                else:
                    logger.warning(f"⚠️ Не удалось получить участников для {chat_type} {chat.id}")
            elif chat_type == "channel":
                logger.info(f"Канал {chat.id} - участники не получаются (это канал, не группа)")
            
            return {
                "success": True,
                "chat_id": chat.id,
                "title": chat.title,
                "chat_type": chat_type,
                "members": members,
                "error": None
            }
        except (PeerIdInvalid, UsernameNotOccupied, UsernameInvalid, ChannelPrivate) as e:
            return {
                "success": False,
                "chat_id": None,
                "title": None,
                "chat_type": None,
                "members": None,
                "error": f"Чат не найден или недоступен: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Ошибка при получении информации о чате {chat_username}: {e}", exc_info=True)
            return {
                "success": False,
                "chat_id": None,
                "title": None,
                "chat_type": None,
                "members": None,
                "error": str(e)
            }
    
    except Exception as e:
        logger.error(f"Ошибка при получении информации о чате: {e}", exc_info=True)
        return {
            "success": False,
            "chat_id": None,
            "title": None,
            "chat_type": None,
            "members": None,
            "error": str(e)
        }


async def get_group_members(user_id: int, group_id: int, use_telethon: bool = False) -> List[int]:
    """
    Получить список участников группы
    
    Args:
        user_id: ID пользователя бота
        group_id: ID группы (chat_id)
        use_telethon: Использовать Telethon вместо Pyrogram (если доступен)
    
    Returns:
        List[int] - список user_id участников группы
    """
    # Пробуем использовать Telethon, если запрошено и доступно
    if use_telethon:
        try:
            return await get_group_members_telethon(user_id, group_id)
        except ImportError:
            logger.warning("Telethon не установлен, используем Pyrogram")
        except Exception as e:
            logger.warning(f"Ошибка при использовании Telethon, переключаемся на Pyrogram: {e}")
    
    try:
        client = await get_user_client(user_id)
        
        if client is None:
            logger.warning(f"Client API не настроен для пользователя {user_id}")
            return []
        
        members = []
        
        # Получаем участников группы через Pyrogram
        try:
            logger.info(f"Начинаем получение участников группы {group_id} через Pyrogram...")
            count = 0
            async for member in client.get_chat_members(group_id):
                count += 1
                # Пропускаем ботов и самого себя
                if member.user.is_bot or member.user.is_self:
                    continue
                
                # Добавляем user_id участника
                if member.user.id:
                    members.append(member.user.id)
                
                # Логируем прогресс для больших групп
                if count % 100 == 0:
                    logger.info(f"Обработано {count} участников, уникальных пользователей: {len(members)}")
            
            logger.info(f"Найдено {len(members)} уникальных участников из {count} всего в группе {group_id}")
            
        except ChatAdminRequired:
            logger.warning(f"Нет прав администратора для получения участников группы {group_id}")
            return []
        except Exception as e:
            logger.warning(f"Ошибка при получении участников группы {group_id} через Pyrogram: {e}")
            # Пробуем альтернативный способ через Telethon, если доступен
            if not use_telethon:
                try:
                    logger.info("Пробуем использовать Telethon как альтернативу...")
                    return await get_group_members(user_id, group_id, use_telethon=True)
                except:
                    pass
            return []
        
        return members
        
    except Exception as e:
        logger.error(f"Ошибка при получении участников группы {group_id}: {e}", exc_info=True)
        return []


async def get_group_members_telethon(user_id: int, group_id: int) -> List[int]:
    """
    Получить список участников группы через Telethon
    
    Args:
        user_id: ID пользователя бота
        group_id: ID группы (chat_id)
    
    Returns:
        List[int] - список user_id участников группы
    """
    try:
        from telethon import TelegramClient
        from telethon.tl.functions.channels import GetParticipantsRequest
        from telethon.tl.types import ChannelParticipantsSearch
        from telethon.errors import ChatAdminRequiredError, UserNotParticipantError
        import os
        
        # Получаем данные пользователя для Telethon
        user = await crud.get_user_by_telegram_id(user_id)
        if not user:
            raise ValueError(f"Пользователь {user_id} не найден в БД")
        
        # Используем данные пользователя или общие из .env
        api_id = user.api_id if user.api_id else API_ID
        api_hash = user.api_hash if user.api_hash else API_HASH
        phone = user.phone_number if user.phone_number else PHONE_NUMBER
        
        if not api_id or not api_hash or not phone:
            raise ValueError("API_ID, API_HASH или PHONE_NUMBER не настроены")
        
        # Создаем клиент Telethon с уникальным именем сессии
        session_dir = "telethon_sessions"
        os.makedirs(session_dir, exist_ok=True)
        session_name = os.path.join(session_dir, f"telethon_{user_id}")
        client = TelegramClient(session_name, api_id, api_hash)
        
        members = []
        
        try:
            # Подключаемся к Telegram
            if not client.is_connected():
                await client.start(phone=phone)
            
            # Получаем участников через Telethon
            logger.info(f"Начинаем получение участников группы {group_id} через Telethon...")
            
            # Получаем entity группы
            try:
                entity = await client.get_entity(group_id)
            except Exception as e:
                # Пробуем получить через username или другой способ
                logger.warning(f"Не удалось получить entity для {group_id}, пробуем альтернативный способ: {e}")
                # Если это числовой ID, пробуем преобразовать
                if isinstance(group_id, int):
                    entity = await client.get_entity(int(f"-100{group_id}"))
                else:
                    raise
            
            # Получаем всех участников
            offset = 0
            limit = 200
            total = 0
            unique_members = set()
            
            while True:
                try:
                    participants = await client(GetParticipantsRequest(
                        entity,
                        ChannelParticipantsSearch(''),
                        offset,
                        limit,
                        hash=0
                    ))
                except ChatAdminRequiredError:
                    logger.warning(f"Нет прав администратора для получения участников группы {group_id} через Telethon")
                    break
                except UserNotParticipantError:
                    logger.warning(f"Пользователь не является участником группы {group_id}")
                    break
                
                if not participants.users:
                    break
                
                for user_obj in participants.users:
                    # Пропускаем ботов
                    if user_obj.bot:
                        continue
                    # Добавляем user_id (используем set для уникальности)
                    if user_obj.id and user_obj.id not in unique_members:
                        unique_members.add(user_obj.id)
                        members.append(user_obj.id)
                
                total += len(participants.users)
                offset += len(participants.users)
                
                logger.info(f"Обработано {total} участников, уникальных пользователей: {len(members)}")
                
                if len(participants.users) < limit:
                    break
            
            logger.info(f"Найдено {len(members)} уникальных участников из {total} всего в группе {group_id} через Telethon")
            
        except ChatAdminRequiredError:
            logger.warning(f"Нет прав администратора для получения участников группы {group_id} через Telethon")
            return []
        except UserNotParticipantError:
            logger.warning(f"Пользователь не является участником группы {group_id}")
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении участников через Telethon: {e}", exc_info=True)
            return []
        finally:
            try:
                if client.is_connected():
                    await client.disconnect()
            except:
                pass
        
        return members
        
    except ImportError:
        raise ImportError("Telethon не установлен. Установите: pip install telethon")
    except Exception as e:
        logger.error(f"Ошибка при использовании Telethon: {e}", exc_info=True)
        raise


async def close_client():
    """Закрыть все клиенты"""
    global _clients
    
    for user_id, client in _clients.items():
        try:
            if client.is_connected:
                await client.stop()
        except Exception as e:
            logger.warning(f"Ошибка при закрытии Client для {user_id}: {e}")
    
    _clients.clear()
    logger.info("Все Telegram Clients закрыты")

