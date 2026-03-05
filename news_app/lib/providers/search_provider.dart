import 'package:flutter/material.dart';

import '../core/utils/debouncer.dart';
import '../models/article_model.dart';
import '../repositories/article_repository.dart';

class SearchProvider extends ChangeNotifier {
  SearchProvider(this._articleRepository)
    : _debouncer = Debouncer(delay: const Duration(milliseconds: 350));

  final ArticleRepository _articleRepository;
  final Debouncer _debouncer;

  List<ArticleModel> _results = <ArticleModel>[];
  bool _isLoading = false;
  String? _error;
  String _query = '';

  List<ArticleModel> get results => _results;
  bool get isLoading => _isLoading;
  String? get error => _error;
  String get query => _query;

  void onQueryChanged(String value) {
    _query = value;
    _error = null;
    notifyListeners();

    _debouncer.run(() async {
      if (_query.trim().isEmpty) {
        _results = <ArticleModel>[];
        _isLoading = false;
        notifyListeners();
        return;
      }

      _isLoading = true;
      notifyListeners();

      final result = await _articleRepository.searchArticles(_query);
      if (result.isSuccess && result.data != null) {
        _results = result.data!;
      } else {
        _error = result.error;
      }

      _isLoading = false;
      notifyListeners();
    });
  }

  @override
  void dispose() {
    _debouncer.dispose();
    super.dispose();
  }
}
