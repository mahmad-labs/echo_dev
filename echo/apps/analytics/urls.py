from echo.common.router import build_app_router
router = build_app_router('analytics')
urlpatterns = router.urls
