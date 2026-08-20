from echo.common.router import build_app_router
router = build_app_router('memory')
urlpatterns = router.urls
