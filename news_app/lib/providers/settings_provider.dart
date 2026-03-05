import 'package:flutter/material.dart';

import '../core/theme/theme_provider.dart';
import '../repositories/settings_repository.dart';

class SettingsProvider extends ChangeNotifier {
  SettingsProvider(this._settingsRepository, this._themeProvider) {
    _followedCategoryIds = _settingsRepository.getFollowedCategories();
    _themeProvider.setDarkMode(_settingsRepository.getThemeIsDark());
    _themeProvider.setFontScale(_settingsRepository.getFontScale());
  }

  final SettingsRepository _settingsRepository;
  final ThemeProvider _themeProvider;

  late Set<int> _followedCategoryIds;

  Set<int> get followedCategoryIds => Set<int>.from(_followedCategoryIds);
  bool get isDarkMode => _themeProvider.isDark;
  double get fontScale => _themeProvider.fontScale;

  void toggleCategoryFollow(int categoryId) {
    if (_followedCategoryIds.contains(categoryId)) {
      _followedCategoryIds.remove(categoryId);
    } else {
      _followedCategoryIds.add(categoryId);
    }
    _settingsRepository.setFollowedCategories(_followedCategoryIds);
    notifyListeners();
  }

  void setDarkMode(bool value) {
    _settingsRepository.setThemeIsDark(value);
    _themeProvider.setDarkMode(value);
    notifyListeners();
  }

  void setFontScale(double value) {
    _settingsRepository.setFontScale(value);
    _themeProvider.setFontScale(value);
    notifyListeners();
  }
}
