import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../app_scope.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final settings = AppScope.of(context).settingsProvider;
    final categories = AppScope.of(context).homeCategoriesProvider;

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: AnimatedBuilder(
        animation: Listenable.merge([settings, categories]),
        builder: (context, _) {
          return ListView(
            padding: EdgeInsets.all(16.w),
            children: [
              SwitchListTile(
                value: settings.isDarkMode,
                title: const Text('Dark mode'),
                onChanged: settings.setDarkMode,
              ),
              SizedBox(height: 8.h),
              Text('Font size (${settings.fontScale.toStringAsFixed(2)}x)'),
              Slider(
                min: 0.9,
                max: 1.3,
                value: settings.fontScale,
                onChanged: settings.setFontScale,
              ),
              SizedBox(height: 16.h),
              Text(
                'Follow categories',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              SizedBox(height: 8.h),
              for (final category in categories.allCategories)
                CheckboxListTile(
                  value: settings.followedCategoryIds.contains(category.id),
                  title: Text(category.name),
                  onChanged: (_) => settings.toggleCategoryFollow(category.id),
                ),
            ],
          );
        },
      ),
    );
  }
}
