import { type NuxtAxiosInstance } from "@nuxtjs/axios";
import {
  BackedRecord,
  BackendAnswerCombinations,
  BackendResponse,
  BackendSearchRecords,
  BackendAdvanceSearchQuery,
  ResponseWithTotal,
  BackedRecords,
  BackendRecordStatus,
  BackendSimilaritySearchOrder,
  BackendSort,
} from "../types";
import { RecordAnswer } from "@/v1/domain/entities/record/RecordAnswer";
import { Record } from "@/v1/domain/entities/record/Record";
import { Question } from "@/v1/domain/entities/question/Question";
import { RecordCriteria } from "@/v1/domain/entities/record/RecordCriteria";
import { Pagination } from "@/v1/domain/entities/Pagination";
import { SimilarityOrder } from "@/v1/domain/entities/similarity/SimilarityCriteria";
import { RangeValue, ValuesOption } from "~/v1/domain/entities/common/Filter";

const RECORD_API_ERRORS = {
  ERROR_FETCHING_RECORDS: "ERROR_FETCHING_RECORDS",
  ERROR_FETCHING_RECORD_BY_ID: "ERROR_FETCHING_RECORD_BY_ID",
  ERROR_DELETING_RECORD_RESPONSE: "ERROR_DELETING_RECORD_RESPONSE",
  ERROR_UPDATING_RECORD_RESPONSE: "ERROR_UPDATING_RECORD_RESPONSE",
  ERROR_CREATING_RECORD_RESPONSE: "ERROR_CREATING_RECORD_RESPONSE",
};

const BACKEND_ORDER: {
  [key in SimilarityOrder]: BackendSimilaritySearchOrder;
} = {
  most: "most_similar",
  least: "least_similar",
};

export class RecordRepository {
  constructor(private readonly axios: NuxtAxiosInstance) {}

  getRecords(
    criteria: RecordCriteria,
    pagination: Pagination
  ): Promise<BackedRecords> {
    if (criteria.isFilteringByAdvanceSearch)
      return this.getRecordsByAdvanceSearch(criteria, pagination);

    return this.getRecordsByDatasetId(criteria, pagination);
  }

  async getRecord(recordId: string): Promise<BackedRecord> {
    try {
      const url = `/v1/records/${recordId}`;

      const { data } = await this.axios.get<BackedRecord>(url);

      return data;
    } catch (err) {
      throw {
        response: RECORD_API_ERRORS.ERROR_FETCHING_RECORD_BY_ID,
      };
    }
  }

  async deleteRecordResponse(record: Record) {
    if (!record.answer) return;

    try {
      await this.axios.delete(`/v1/responses/${record.answer.id}`);
    } catch (error) {
      throw {
        response: RECORD_API_ERRORS.ERROR_DELETING_RECORD_RESPONSE,
      };
    }
  }

  discardRecordResponse(record: Record): Promise<RecordAnswer> {
    if (record.answer) return this.updateRecordResponse(record, "discarded");

    return this.createRecordResponse(record, "discarded");
  }

  submitNewRecordResponse(record: Record): Promise<RecordAnswer> {
    if (record.answer) return this.updateRecordResponse(record, "submitted");

    return this.createRecordResponse(record, "submitted");
  }

  saveDraft(record: Record): Promise<RecordAnswer> {
    if (record.answer) return this.updateRecordResponse(record, "draft");

    return this.createRecordResponse(record, "draft");
  }

  private async updateRecordResponse(
    record: Record,
    status: BackendRecordStatus
  ) {
    try {
      const request = this.createRequest(status, record.questions);

      const { data } = await this.axios.put<BackendResponse>(
        `/v1/responses/${record.answer.id}`,
        request
      );

      return new RecordAnswer(data.id, status, data.values, data.updated_at);
    } catch (error) {
      throw {
        response: RECORD_API_ERRORS.ERROR_UPDATING_RECORD_RESPONSE,
      };
    }
  }

  private async createRecordResponse(
    record: Record,
    status: BackendRecordStatus
  ) {
    try {
      const request = this.createRequest(status, record.questions);

      const { data } = await this.axios.post<BackendResponse>(
        `/v1/records/${record.id}/responses`,
        request
      );

      return new RecordAnswer(
        data.id,
        data.status,
        data.values,
        data.updated_at
      );
    } catch (error) {
      throw {
        response: RECORD_API_ERRORS.ERROR_CREATING_RECORD_RESPONSE,
      };
    }
  }

  private async getRecordsByDatasetId(
    criteria: RecordCriteria,
    pagination: Pagination
  ): Promise<BackedRecords> {
    const { datasetId, status } = criteria;
    const { from, many } = pagination;
    try {
      const url = `/v1/me/datasets/${datasetId}/records`;

      const params = this.createParams(from, many, status);

      const { data } = await this.axios.get<ResponseWithTotal<BackedRecord[]>>(
        url,
        {
          params,
        }
      );
      const { items: records, total } = data;

      return {
        records,
        total,
      };
    } catch (err) {
      throw {
        response: RECORD_API_ERRORS.ERROR_FETCHING_RECORDS,
      };
    }
  }

  private async getRecordsByAdvanceSearch(
    criteria: RecordCriteria,
    pagination: Pagination
  ): Promise<BackedRecords> {
    const {
      datasetId,
      status,
      searchText,
      metadata,
      sortBy,
      similaritySearch,
      response,
      suggestion,
      isFilteringByText,
      isFilteringByMetadata,
      isFilteringBySimilarity,
      isFilteringByResponse,
      isFilteringBySuggestion,
      isSortingBy,
    } = criteria;
    const { from, many } = pagination;

    try {
      const url = `/v1/me/datasets/${datasetId}/records/search`;

      const body: BackendAdvanceSearchQuery = {
        query: {},
      };

      if (isFilteringBySimilarity) {
        body.query.vector = {
          name: similaritySearch.vectorName,
          record_id: similaritySearch.recordId,
          max_results: similaritySearch.limit,
          order: BACKEND_ORDER[similaritySearch.order],
        };
      }

      if (isFilteringByText) {
        body.query.text = {
          q: searchText,
        };
      }

      if (
        isFilteringByMetadata ||
        isFilteringByResponse ||
        isFilteringBySuggestion
      ) {
        body.filters = {
          and: [],
        };
      }

      if (isFilteringByMetadata) {
        metadata.value.forEach((m) => {
          const range = m.value as RangeValue;

          if ("ge" in range && "le" in range) {
            body.filters.and.push({
              type: "range",
              scope: {
                entity: "metadata",
                metadata_property: m.name,
              },
              ge: range.ge,
              le: range.le,
            });

            return;
          }

          body.filters.and.push({
            type: "terms",
            scope: {
              entity: "metadata",
              metadata_property: m.name,
            },
            values: m.value as string[],
          });
        });
      }

      if (isFilteringByResponse) {
        response.or.forEach((r) => {
          const value = r.value as RangeValue;
          if ("ge" in value && "le" in value) {
            body.filters.and.push({
              type: "range",
              scope: {
                entity: "response",
                question: r.name,
              },
              ge: value.ge,
              le: value.le,
            });
            return;
          }
          body.filters.and.push({
            type: "terms",
            scope: {
              entity: "response",
              question: r.name,
            },
            values: r.value as string[],
          });
        });

        response.and.forEach((r) => {
          body.filters.and.push({
            type: "terms",
            scope: {
              entity: "response",
              question: r.name,
            },
            values: [r.value],
          });
        });
      }

      if (isFilteringBySuggestion) {
        suggestion.or.forEach((suggestion) => {
          if (suggestion.configuration.name === "score") {
            const value = suggestion.configuration.value as RangeValue;

            body.filters.and.push({
              type: "range",
              scope: {
                entity: "suggestion",
                question: suggestion.question.name,
                property: suggestion.configuration.name,
              },
              ge: value.ge,
              le: value.le,
            });
          }

          if (suggestion.configuration.name === "value") {
            const value = suggestion.configuration.value as RangeValue;

            if ("ge" in value && "le" in value) {
              body.filters.and.push({
                type: "range",
                scope: {
                  entity: "suggestion",
                  question: suggestion.question.name,
                  property: suggestion.configuration.name,
                },
                ge: value.ge,
                le: value.le,
              });

              return;
            }

            const valuesOptions = suggestion.configuration
              .value as ValuesOption;

            body.filters.and.push({
              type: "terms",
              scope: {
                entity: "suggestion",
                question: suggestion.question.name,
                property: suggestion.configuration.name,
              },
              values: valuesOptions.values,
            });
          }

          if (suggestion.configuration.name === "agent") {
            const values = suggestion.configuration.value as string[];

            body.filters.and.push({
              type: "terms",
              scope: {
                entity: "suggestion",
                question: suggestion.question.name,
                property: suggestion.configuration.name,
              },
              values,
            });
          }
        });

        suggestion.and.forEach((suggestion) => {
          body.filters.and.push({
            type: "terms",
            scope: {
              entity: "suggestion",
              question: suggestion.question.name,
              property: suggestion.configuration.name,
            },
            values: [suggestion.configuration.value],
          });
        });
      }

      if (isSortingBy) {
        body.sort = [];

        sortBy.value.forEach((sort) => {
          const backendSort: BackendSort = {
            scope: {
              entity: sort.entity,
            },
            order: sort.order,
          };

          if (sort.property) {
            backendSort.scope.question = sort.name;
            backendSort.scope.property = sort.property;
          } else if (sort.entity === "response") {
            backendSort.scope.question = sort.name;
          } else if (sort.entity === "metadata") {
            backendSort.scope.metadata_property = sort.name;
          } else if (sort.entity === "record") {
            backendSort.scope.property = sort.name;
          }

          body.sort.push(backendSort);
        });
      }

      const params = this.createParams(from, many, status);

      const { data } = await this.axios.post<
        ResponseWithTotal<BackendSearchRecords[]>
      >(url, body, { params });

      const { items, total } = data;

      const records = items.map((item) => {
        return {
          ...item.record,
          query_score: item.query_score,
        };
      });

      return {
        records,
        total,
      };
    } catch (err) {
      throw {
        response: RECORD_API_ERRORS.ERROR_FETCHING_RECORDS,
      };
    }
  }

  private createRequest(
    status: BackendRecordStatus,
    questions: Question[]
  ): Omit<BackendResponse, "id" | "updated_at"> {
    const values = {} as BackendAnswerCombinations;

    questions
      .filter(
        (question) =>
          question.answer.isValid || question.answer.isPartiallyValid
      )
      .forEach((question) => {
        values[question.name] = { value: question.answer.valuesAnswered };
      });

    return {
      status,
      values,
    };
  }

  private createParams(fromRecord: number, howMany: number, status: string) {
    const offset = `${fromRecord - 1}`;
    const params = new URLSearchParams();

    params.append("include", "responses");
    params.append("include", "suggestions");
    params.append("offset", offset);
    params.append("limit", howMany.toString());
    params.append("response_status", status);

    return params;
  }
}
