from echo.common.router import build_app_router
router = build_app_router('notifications')
urlpatterns = router.urls
