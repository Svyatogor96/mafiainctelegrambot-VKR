import asyncio
from bot.bot import StartBot
from backendapi import init_first_data


async def main() -> None:
    await StartBot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Принудительная остановка.')
