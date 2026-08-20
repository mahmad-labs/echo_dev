from echo.common.router import build_app_router
router = build_app_router('vector_database')
urlpatterns = router.urls
