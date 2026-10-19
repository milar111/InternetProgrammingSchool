from django.contrib import admin
from .models import Capital, Game, GamePlayer, Round, RoundAnswer, Territory


class GamePlayerInline(admin.TabularInline):
    model = GamePlayer
    extra = 0

    def has_add_permission(self, request, obj=None):
        if obj and obj.status != Game.WAITING:
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != Game.WAITING:
            return False
        return super().has_delete_permission(request, obj)


class RoundInline(admin.TabularInline):
    model = Round
    extra = 0


class RoundAnswerInline(admin.TabularInline):
    model = RoundAnswer
    extra = 0


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("id", "created_by", "status", "created_at", "started_at", "finished_at")
    list_filter = ("status", "created_at")
    search_fields = ("created_by__username",)
    inlines = [GamePlayerInline, RoundInline]
    actions = ["initialize_game_action"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.status == Game.WAITING and "status" in form.base_fields:
            # Prevent manually selecting active without initialization
            form.base_fields["status"].choices = [
                c for c in form.base_fields["status"].choices if c[0] not in (Game.ACTIVE, Game.IN_PROGRESS)
            ]
        return form

    @admin.action(description="Initialize selected game(s)")
    def initialize_game_action(self, request, queryset):
        from .services import initialize_game, GameInitializationError
        for game in queryset:
            try:
                initialize_game(game)
                self.message_user(request, f"Game #{game.id} initialized successfully.")
            except GameInitializationError as e:
                self.message_user(request, f"Failed to initialize Game #{game.id}: {e}", level="error")


@admin.register(GamePlayer)
class GamePlayerAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "user", "player_order", "color", "score", "is_active", "joined_at")
    list_filter = ("is_active", "color", "game")
    search_fields = ("user__username", "game__id")

    def has_delete_permission(self, request, obj=None):
        if obj and obj.game.status != Game.WAITING:
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.game.status != Game.WAITING:
            return ("game", "user", "player_order", "color")
        return ()


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "number", "status", "question_type", "started_at", "finished_at")
    list_filter = ("status", "question_type")
    search_fields = ("game__id",)
    inlines = [RoundAnswerInline]


@admin.register(RoundAnswer)
class RoundAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "round", "player", "is_correct", "points_awarded", "submitted_at")
    list_filter = ("is_correct",)
    search_fields = ("player__user__username",)


@admin.register(Territory)
class TerritoryAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "name", "slug", "owner", "score", "get_neighbors")
    search_fields = ("name", "slug")
    list_filter = ("game", "owner")
    readonly_fields = ("game", "name", "slug", "owner", "neighbors")
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_neighbors(self, obj):
        return ", ".join(t.name for t in obj.neighbors.all())

    get_neighbors.short_description = "Neighbors"


@admin.register(Capital)
class CapitalAdmin(admin.ModelAdmin):
    list_display = ("id", "get_game", "player", "territory", "health")
    search_fields = ("player__user__username", "territory__name", "territory__slug")
    list_filter = ("territory__game",)
    readonly_fields = ("player", "territory")
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_game(self, obj):
        return obj.game

    get_game.short_description = "Game"
