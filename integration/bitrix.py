import aiohttp

from config import GlobalSettings


class BitrixLeadAdd:
    # Инициализация класса для создания лидов в Bitrix24.
    def __init__(self, WebHookUrl: str):
        self.LeadAddWebHook = WebHookUrl

    async def create_lead(self, lead_fields):#, telegram_id, ):
    #Создание нового лида в Bitrix24 с использованием метода crm.lead.add.

        Lead_fields = lead_fields

        url = f"{self.LeadAddWebHook}/crm.lead.add.json"
        data = {
            "fields": Lead_fields,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                #TODO удалить принты позже
                print(data)
                print(response)

                return await response.json()