from echo.common.router import build_app_router
router = build_app_router('code_assistant')
urlpatterns = router.urls
