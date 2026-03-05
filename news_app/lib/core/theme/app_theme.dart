import 'package:flutter/material.dart';

class AppTheme {
  static ThemeData light(double fontScale) {
    final base = ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: Colors.white,
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0F172A)),
    );
    return base.copyWith(
      cardTheme: const CardThemeData(elevation: 0),
      textTheme: base.textTheme.apply(fontSizeFactor: fontScale),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.white,
        elevation: 0,
      ),
    );
  }

  static ThemeData dark(double fontScale) {
    final base = ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: const Color(0xFF1F2937),
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFF38BDF8),
        brightness: Brightness.dark,
      ),
    );
    return base.copyWith(
      cardTheme: const CardThemeData(elevation: 0),
      textTheme: base.textTheme.apply(fontSizeFactor: fontScale),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF1F2937),
        elevation: 0,
      ),
    );
  }
}
