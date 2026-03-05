import 'package:flutter/material.dart';

import '../models/category_model.dart';
import '../repositories/category_repository.dart';
import 'settings_provider.dart';

class HomeCategoriesProvider extends ChangeNotifier {
  HomeCategoriesProvider(this._categoryRepository, this._settingsProvider) {
    _settingsProvider.addListener(_onSettingsChanged);
  }

  final CategoryRepository _categoryRepository;
  final SettingsProvider _settingsProvider;

  List<CategoryModel> _allCategories = <CategoryModel>[];
  bool _isLoading = false;
  String? _error;
  int _visibleLimit = 6;

  bool get isLoading => _isLoading;
  String? get error => _error;
  List<CategoryModel> get allCategories => _allCategories;

  List<CategoryModel> get visibleCategories {
    final followed = _settingsProvider.followedCategoryIds;
    final source = followed.isEmpty
        ? _allCategories
        : _allCategories
              .where((c) => followed.contains(c.id))
              .toList(growable: false);
    if (followed.isNotEmpty) return source;
    final end = _visibleLimit > source.length ? source.length : _visibleLimit;
    return source.sublist(0, end);
  }

  bool get canLoadMoreWhenUnfiltered {
    return _settingsProvider.followedCategoryIds.isEmpty &&
        _visibleLimit < _allCategories.length;
  }

  Future<void> fetchInitial() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    final result = await _categoryRepository.fetchCategories();
    if (result.isSuccess && result.data != null) {
      _allCategories = result.data!;
      _visibleLimit = 6;
    } else {
      _error = result.error;
    }

    _isLoading = false;
    notifyListeners();
  }

  void loadMore() {
    if (!canLoadMoreWhenUnfiltered) return;
    _visibleLimit += 6;
    notifyListeners();
  }

  void _onSettingsChanged() {
    notifyListeners();
  }

  @override
  void dispose() {
    _settingsProvider.removeListener(_onSettingsChanged);
    super.dispose();
  }
}
