import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'package:loadmore/loadmore.dart';

import '../../app_scope.dart';
import '../../models/category_model.dart';
import '../../widgets/article/article_list_item.dart';
import '../../widgets/common/app_refresh_indicator.dart';
import '../../widgets/common/empty_state.dart';
import '../../widgets/common/error_state.dart';
import '../../widgets/common/loading_indicator.dart';
import '../article_detail/article_detail_screen.dart';

class CategoryScreen extends StatefulWidget {
  const CategoryScreen({super.key, required this.category});

  final CategoryModel category;

  @override
  State<CategoryScreen> createState() => _CategoryScreenState();
}

class _CategoryScreenState extends State<CategoryScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      AppScope.of(
        context,
      ).categoryArticlesProvider.fetchInitial(widget.category.id);
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = AppScope.of(context).categoryArticlesProvider;
    final categoryId = widget.category.id;

    return Scaffold(
      appBar: AppBar(title: Text(widget.category.name)),
      body: AnimatedBuilder(
        animation: provider,
        builder: (context, _) {
          final items = provider.items(categoryId);
          if (provider.isLoadingInitial(categoryId)) {
            return const LoadingIndicator();
          }
          if (provider.error(categoryId) != null && items.isEmpty) {
            return ErrorState(
              message: provider.error(categoryId)!,
              onRetry: () => provider.fetchInitial(categoryId),
            );
          }
          if (items.isEmpty) {
            return const EmptyState(message: 'No articles in this category.');
          }

          return AppRefreshIndicator(
            onRefresh: () => provider.fetchInitial(categoryId),
            child: LoadMore(
              isFinish: !provider.hasMore(categoryId),
              onLoadMore: () async {
                if (provider.isLoadingMore(categoryId) ||
                    !provider.hasMore(categoryId)) {
                  return false;
                }
                await provider.fetchMore(categoryId);
                return provider.hasMore(categoryId);
              },
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: EdgeInsets.all(16.w),
                children: [
                  for (final article in items)
                    ArticleListItem(
                      article: article,
                      onTap: () {
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) =>
                                ArticleDetailScreen(articleId: article.id),
                          ),
                        );
                      },
                    ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
