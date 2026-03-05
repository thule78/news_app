import 'package:flutter/material.dart';

class ThemeProvider extends ChangeNotifier {
  bool _isDark = false;
  double _fontScale = 1.0;

  bool get isDark => _isDark;
  double get fontScale => _fontScale;

  ThemeMode get themeMode => _isDark ? ThemeMode.dark : ThemeMode.light;

  void setDarkMode(bool value) {
    if (_isDark == value) return;
    _isDark = value;
    notifyListeners();
  }

  void setFontScale(double value) {
    final clamped = value.clamp(0.9, 1.3);
    if (_fontScale == clamped) return;
    _fontScale = clamped;
    notifyListeners();
  }
}
