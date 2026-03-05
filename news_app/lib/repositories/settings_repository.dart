class SettingsRepository {
  final Set<int> _followedCategoryIds = <int>{};
  bool _isDark = false;
  double _fontScale = 1.0;

  Set<int> getFollowedCategories() => Set<int>.from(_followedCategoryIds);
  bool getThemeIsDark() => _isDark;
  double getFontScale() => _fontScale;

  void setFollowedCategories(Set<int> ids) {
    _followedCategoryIds
      ..clear()
      ..addAll(ids);
  }

  void setThemeIsDark(bool isDark) {
    _isDark = isDark;
  }

  void setFontScale(double scale) {
    _fontScale = scale;
  }
}
