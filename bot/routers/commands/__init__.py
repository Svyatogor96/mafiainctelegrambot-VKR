__all__ = ("router",)

from aiogram import Router
from .user_commands import router as user_commands_router
from .user_commands_profile import router as user_commands_router_profile
from .registration_commands import router as registration_router
from .admin_commands import router as admin_commands_router
from .admin_places_editor import router as admin_places_router
from .admin_billboard import router as admin_billboard_router
from .admin_reports import router as admin_reports_router

from .su_admin import router as su_admin_router
from .common import router as common_router

router = Router(name=__name__)
router.include_routers(user_commands_router, user_commands_router_profile,
                       registration_router, admin_commands_router, admin_places_router,
                       admin_billboard_router, admin_reports_router, su_admin_router)

# этот роутер должен быть подключен всегда последним, поскольку назначен
# для обработки сообщений никем и никак не обработанных
router.include_router(common_router)
