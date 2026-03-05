import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../app_scope.dart';
import '../../core/utils/date_formatters.dart';
import '../../widgets/common/empty_state.dart';
import '../../widgets/common/loading_indicator.dart';
import '../article_detail/article_detail_screen.dart';

class SearchScreen extends StatelessWidget {
  const SearchScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = AppScope.of(context).searchProvider;

    return Scaffold(
      appBar: AppBar(title: const Text('Search')),
      body: Padding(
        padding: EdgeInsets.all(16.w),
        child: Column(
          children: [
            TextField(
              onChanged: provider.onQueryChanged,
              decoration: const InputDecoration(
                hintText: 'Search by title',
                border: OutlineInputBorder(),
              ),
            ),
            SizedBox(height: 12.h),
            Expanded(
              child: AnimatedBuilder(
                animation: provider,
                builder: (context, _) {
                  if (provider.isLoading) return const LoadingIndicator();
                  if (provider.query.isEmpty) {
                    return const EmptyState(
                      message: 'Type to search articles.',
                    );
                  }
                  if (provider.results.isEmpty) {
                    return const EmptyState(message: 'No results found.');
                  }

                  return ListView.builder(
                    itemCount: provider.results.length,
                    itemBuilder: (context, index) {
                      final article = provider.results[index];
                      return ListTile(
                        title: Text(
                          article.title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        subtitle: Text(
                          '${article.categoryName} • ${article.author} • ${DateFormatters.shortDate(article.publishedAt)}\n${article.description}',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        onTap: () {
                          Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) =>
                                  ArticleDetailScreen(articleId: article.id),
                            ),
                          );
                        },
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
