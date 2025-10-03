from fastapi import APIRouter
from .post_analysis import router as post_analysis_router
from .network_query import router as network_query_router
from .warm_intro import router as warm_intro_router
from .chat import router as chat_router
from .ghost_ask import router as ghost_ask_router

# Combine all routers
api_router = APIRouter()

api_router.include_router(post_analysis_router)
api_router.include_router(network_query_router)
api_router.include_router(warm_intro_router)
api_router.include_router(chat_router)
api_router.include_router(ghost_ask_router)

__all__ = ["api_router"]

